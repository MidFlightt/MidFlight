"""PigeonPost: wires the five API parts together. Each part edits only its own file."""

from fastapi import FastAPI

from app import billing, dispatch, pricing, roost, tracking

app = FastAPI(title="PigeonPost")
app.include_router(roost.router)
app.include_router(pricing.router)
app.include_router(dispatch.router)
app.include_router(billing.router)
app.include_router(tracking.router)
