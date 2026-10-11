"""Pricing: what a parcel costs."""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import roost

router = APIRouter()

CENT = Decimal("0.01")


class QuoteRequest(BaseModel):
    destination: str
    weight_kg: float
    promo: str | None = None
    express: bool = False


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def price(destination: str, weight_kg: float, promo: str | None, express: bool) -> dict:
    """The quote for one parcel. Raises ValueError with a message for the customer."""
    place = roost.get_destination(destination)
    if place is None:
        raise ValueError(f"no destination called {destination}")
    weight = Decimal(str(weight_kg))
    if weight < Decimal("0.5") or weight % Decimal("0.5") != 0:
        raise ValueError("weight must be a multiple of 0.5 kg, from 0.5")
    if promo not in (None, "", "COOCOO"):
        raise ValueError(f"unknown promo code {promo}")
    fee = cents(Decimal("4.00") + Decimal("0.50") * place["distance_km"] + Decimal("2.00") * weight)
    discount = cents(fee * Decimal("0.15")) if promo == "COOCOO" else Decimal("0.00")
    express_fee = cents(fee * Decimal("0.50")) if express else Decimal("0.00")
    tax = cents((fee - discount + express_fee) * Decimal("0.08"))
    return {
        "delivery_fee": float(fee),
        "promo_discount": float(discount),
        "express_fee": float(express_fee),
        "tax": float(tax),
        "total": float(fee - discount + express_fee + tax),
    }


@router.post("/quote")
def quote(request: QuoteRequest) -> dict:
    try:
        return price(request.destination, request.weight_kg, request.promo, request.express)
    except ValueError as problem:
        raise HTTPException(400, str(problem)) from problem
