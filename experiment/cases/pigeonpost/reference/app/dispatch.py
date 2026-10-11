"""Dispatch: sends, shows, and cancels deliveries; tracks each bird's flights left."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException

from app import pricing, roost

router = APIRouter()

DELIVERIES: dict[int, dict] = {}
CANCELLATION_FEE = Decimal("0.25")  # the lead's decision


def list_deliveries() -> list[dict]:
    return list(DELIVERIES.values())


def get_delivery(delivery_id: int) -> dict | None:
    return DELIVERIES.get(delivery_id)


def flights_left(handle: str) -> int:
    bird = roost.get_bird(handle)
    used = sum(d["bird"] == handle and d["status"] == "confirmed" for d in list_deliveries())
    return bird["flights_per_day"] - used


def cancellation_fee(total: float) -> float:
    return float(pricing.cents(Decimal(str(total)) * CANCELLATION_FEE))


@router.post("/deliveries")
def send(request: pricing.QuoteRequest) -> dict:
    try:
        quote = pricing.price(request.destination, request.weight_kg, request.promo,
                              request.express)  # fmt: skip
    except ValueError as problem:
        raise HTTPException(400, str(problem)) from problem
    strong_enough = [b for b in roost.BIRDS if b["max_payload"] >= request.weight_kg]
    if not strong_enough:
        raise HTTPException(400, "too heavy for any bird")
    free = [b for b in strong_enough if flights_left(b["handle"]) > 0]
    if not free:
        raise HTTPException(400, "no bird that can carry it has a flight left today")
    bird = min(free, key=lambda b: b["max_payload"])
    delivery = {
        "id": len(DELIVERIES) + 1,
        "destination": request.destination,
        "weight_kg": request.weight_kg,
        "bird": bird["handle"],
        "status": "confirmed",
        "total": quote["total"],
        "refund": 0.0,
    }
    DELIVERIES[delivery["id"]] = delivery
    return delivery


@router.get("/deliveries/{delivery_id}")
def show(delivery_id: int) -> dict:
    delivery = get_delivery(delivery_id)
    if delivery is None:
        raise HTTPException(404, f"no delivery {delivery_id}")
    return delivery


@router.post("/deliveries/{delivery_id}/cancel")
def cancel(delivery_id: int) -> dict:
    delivery = show(delivery_id)
    if delivery["status"] != "cancelled":
        delivery["status"] = "cancelled"
        fee = cancellation_fee(delivery["total"])
        delivery["refund"] = round(delivery["total"] - fee, 2)
    return delivery


@router.get("/birds/{handle}/availability")
def availability(handle: str) -> dict:
    if roost.get_bird(handle) is None:
        raise HTTPException(404, f"no bird called {handle}")
    return {"bird": handle, "flights_left": flights_left(handle)}
