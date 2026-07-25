from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        code: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.extra = extra or {}


def error_payload(detail: str, code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "detail": detail,
        "code": code,
        "extra": extra or {},
    }


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.detail, exc.code, exc.extra),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "요청을 처리할 수 없습니다."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(detail, "HTTP_ERROR"),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            "요청 값이 올바르지 않습니다.",
            "VALIDATION_ERROR",
            {"errors": exc.errors()},
        ),
    )
