"""HireBot: wires the three parts together. Each part edits only its own file."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import catalog, hiring

app = FastAPI(title="HireBot")
app.include_router(catalog.router)
app.include_router(hiring.router)
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True))
