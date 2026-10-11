"""Billing: the revenue report."""

from fastapi import APIRouter

from app import dispatch

router = APIRouter()


@router.get("/report")
def report() -> dict:
    revenue = 0.0
    flights: dict[str, int] = {}
    confirmed = cancelled = 0
    for delivery in dispatch.list_deliveries():
        if delivery["status"] == "confirmed":
            confirmed += 1
            revenue += delivery["total"]
            flights[delivery["bird"]] = flights.get(delivery["bird"], 0) + 1
        else:
            cancelled += 1
            revenue += delivery["total"] - delivery["refund"]  # the cancellation fee
    return {
        "revenue": round(revenue, 2),
        "confirmed": confirmed,
        "cancelled": cancelled,
        "flights": flights,
    }
