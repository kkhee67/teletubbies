import os

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    validation_exception_handler,
)
from routers.analysis import router as analysis_router
from routers.properties import router as properties_router


DEFAULT_CORS_ALLOW_ORIGINS = [
    "http://localhost:3000",
    "https://dive-2026-teletubbies.hgumax.chatgpt.site",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_allow_origins() -> list[str]:
    value = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    return origins or DEFAULT_CORS_ALLOW_ORIGINS


app = FastAPI(title="안심계약 레이더 API", version="0.2.0")

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties_router)
app.include_router(analysis_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
