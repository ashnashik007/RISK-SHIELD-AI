from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine, Base, SessionLocal
from . import seed
from .routers import transactions, investigations, simulator, policies, analytics, audit, stream

app = FastAPI(title="RiskShield AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed.seed_if_empty(db)
    finally:
        db.close()


app.include_router(transactions.router)
app.include_router(investigations.router)
app.include_router(simulator.router)
app.include_router(policies.router)
app.include_router(analytics.router)
app.include_router(audit.router)
app.include_router(stream.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the frontend (index.html, styles.css, app.js) from the same server,
# so the whole app is a single `uvicorn app.main:app` away from running.
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
