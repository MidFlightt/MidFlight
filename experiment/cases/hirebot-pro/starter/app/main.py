"""HireBot: wires the four API parts together. Each part edits only its own file."""

from fastapi import FastAPI

from app import bookings, catalog, pricing, reports

app = FastAPI(title="HireBot")
app.include_router(catalog.router)
app.include_router(pricing.router)
app.include_router(bookings.router)
app.include_router(reports.router)
