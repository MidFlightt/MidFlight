"""Tracking: where a delivery is, and when it lands."""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException

from app import dispatch, roost

router = APIRouter()


@router.get("/deliveries/{delivery_id}/tracking")
def tracking(delivery_id: int) -> dict:
    delivery = dispatch.get_delivery(delivery_id)
    if delivery is None:
        raise HTTPException(404, f"no delivery {delivery_id}")
    eta = 0
    if delivery["status"] == "confirmed":
        distance = Decimal(str(roost.get_destination(delivery["destination"])["distance_km"]))
        speed = Decimal(str(roost.get_bird(delivery["bird"])["speed"]))
        eta = int((distance / speed * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {
        "delivery": delivery["id"],
        "status": delivery["status"],
        "bird": delivery["bird"],
        "eta_minutes": eta,
    }
