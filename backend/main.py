from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.analysis import router as analysis_router
from routers.properties import router as properties_router


app = FastAPI(title="안심계약 레이더 API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties_router)
app.include_router(analysis_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
