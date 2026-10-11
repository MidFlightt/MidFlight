"""Roost: the birds and the destinations."""

from fastapi import APIRouter, HTTPException

router = APIRouter()

BIRDS = [
    {"handle": "budget-bob", "name": "Budget Bob", "max_payload": 1, "speed": 36,
     "flights_per_day": 2},
    {"handle": "express-edna", "name": "Express Edna", "max_payload": 2, "speed": 90,
     "flights_per_day": 3},
    {"handle": "sir-flaps-a-lot", "name": "Sir Flaps-a-Lot", "max_payload": 3, "speed": 54,
     "flights_per_day": 2},
    {"handle": "cargo-carl", "name": "Cargo Carl", "max_payload": 5, "speed": 45,
     "flights_per_day": 1},
]  # fmt: skip
DESTINATIONS = [
    {"code": "downtown", "name": "Downtown", "distance_km": 3},
    {"code": "harbor", "name": "The Harbor", "distance_km": 8},
    {"code": "campus", "name": "The Campus", "distance_km": 12},
    {"code": "airport", "name": "The Airport", "distance_km": 20},
]


def get_bird(handle: str) -> dict | None:
    return next((b for b in BIRDS if b["handle"] == handle), None)


def get_destination(code: str) -> dict | None:
    return next((d for d in DESTINATIONS if d["code"] == code), None)


@router.get("/birds")
def list_birds() -> list[dict]:
    return BIRDS


@router.get("/birds/{handle}")
def one_bird(handle: str) -> dict:
    bird = get_bird(handle)
    if bird is None:
        raise HTTPException(404, f"no bird called {handle}")
    return bird


@router.get("/destinations")
def list_destinations() -> list[dict]:
    return DESTINATIONS


@router.get("/destinations/{code}")
def one_destination(code: str) -> dict:
    destination = get_destination(code)
    if destination is None:
        raise HTTPException(404, f"no destination called {code}")
    return destination
