import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import patients
from .scheduler import start_scheduler, stop_scheduler, DEMO_SPEEDUP
from .seed import seed
from .ml.model import warm_up as warm_up_ml_model

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    warm_up_ml_model()
    seed()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Aegis Triage API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "aegis-triage"}


@app.get("/api/config")
def config():
    """Exposes the demo time-acceleration factor so the frontend can render
    accurate recheck countdowns. 1 simulated minute = 60/demo_speedup real seconds."""
    return {"demo_speedup": DEMO_SPEEDUP}
