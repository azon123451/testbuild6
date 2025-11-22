from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import engine
from .models import Base
from .routers import internal_router, operator_router

settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shop Support Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(internal_router)
app.include_router(operator_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}

