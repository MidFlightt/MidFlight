"""The adapter's HTTP calls to the Midflight API. Every call sends the agent's token."""

from __future__ import annotations

from typing import Any

import httpx


class MidflightUnavailable(Exception):
    """The API couldn't be reached. Never treated as approval (UC-02 6b)."""


class NotSignedIn(Exception):
    """The API refused the token (401). The fix is a setting (UC-02 6a)."""


class Refused(Exception):
    """The API answered with an error: what was wrong, and how to fix it."""

    def __init__(self, status: int, body: dict[str, Any]) -> None:
        super().__init__(body.get("detail", f"HTTP {status}"))
        self.status = status
        self.body = body


class MidflightApi:
    def __init__(self, http: httpx.Client, project_id: str) -> None:
        self._http = http
        self.project_id = project_id

    @classmethod
    def connect(cls, url: str, token: str, project_id: str, timeout: float = 15) -> MidflightApi:
        http = httpx.Client(
            base_url=url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout
        )
        return cls(http, project_id)

    def check_in(self, task_id: str | None = None) -> dict[str, Any]:
        return self._call("POST", f"/projects/{self.project_id}/check-in", {"task_id": task_id})

    def submit_claim(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", f"/projects/{self.project_id}/claims", body)

    def job(self, job_id: str) -> dict[str, Any]:
        return self._call("GET", f"/jobs/{job_id}")

    def withdraw(self, claim_id: str, reason: str | None) -> dict[str, Any]:
        return self._call("POST", f"/claims/{claim_id}/withdraw", {"reason": reason})

    def close(self, claim_id: str, reason: str | None) -> dict[str, Any]:
        return self._call("POST", f"/claims/{claim_id}/close", {"reason": reason})

    def acknowledge(self, directive_id: str, response: str, note: str | None) -> dict[str, Any]:
        body = {"response": response, "note": note}
        return self._call("POST", f"/directives/{directive_id}/ack", body)

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            response = self._http.request(method, path, json=body)
        except httpx.TransportError as error:
            raise MidflightUnavailable(str(error) or type(error).__name__) from error
        if response.status_code == 401:
            raise NotSignedIn(response.json().get("detail", "unauthorized"))
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {"detail": response.text}
            if response.status_code == 422:
                payload = {"error": "InvalidRequest", "detail": _validation(payload)}
            raise Refused(response.status_code, payload)
        return response.json()


def _validation(payload: dict[str, Any]) -> str:
    errors = payload.get("detail")
    if not isinstance(errors, list):
        return str(errors)
    return "; ".join(
        f"{'.'.join(str(p) for p in e.get('loc', [])[1:])}: {e.get('msg')}" for e in errors
    )
