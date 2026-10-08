"""Errors services raise. The API (M-2) maps each one to an HTTP status."""

from __future__ import annotations

from collections.abc import Sequence

from midflight.domain.models import Finding


class ServiceError(Exception):
    status = 500

    def __init__(self, detail: str, hint: str = "", findings: Sequence[Finding] = ()) -> None:
        super().__init__(detail)
        self.detail = detail
        self.hint = hint
        self.findings = list(findings)


class InvalidRequest(ServiceError):
    """The request can't be accepted as sent. Nothing was saved."""

    status = 400


class PermissionDenied(ServiceError):
    """The caller's role or ownership doesn't allow this (INV-08)."""

    status = 403


class NotFound(ServiceError):
    status = 404


class StateConflict(ServiceError):
    """The entity's current state doesn't allow this, e.g. closing a pending claim."""

    status = 409
