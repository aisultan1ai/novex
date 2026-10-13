from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.core.i18n import LOCALE_HEADER, translate, translate_detail
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.core.middleware import LocaleMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware

settings = get_settings()
setup_logging(level="DEBUG" if settings.debug else "INFO")
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        release=settings.app_version,
    )
    logger.info("Sentry initialised (env=%s)", settings.environment)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s v%s in %s mode",
        settings.project_name,
        settings.app_version,
        settings.environment,
    )
    yield
    logger.info("Shutting down %s", settings.project_name)


_docs_url = None if settings.is_production else "/docs"
_redoc_url = None if settings.is_production else "/redoc"
_openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title=settings.project_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(LocaleMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language", "X-Request-Id", LOCALE_HEADER],
)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": translate(str(exc))})


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": translate(str(exc))})


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": translate(str(exc))})


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(
    request: Request, exc: UnauthorizedError
) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": translate(str(exc))})


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": translate(str(exc))})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTPException из эндпоинтов: тот же ответ, что у FastAPI по умолчанию,
    но detail переведён на язык запроса."""
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": translate_detail(exc.detail)},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Ошибки Pydantic (422): формат FastAPI по умолчанию + перевод msg."""
    return JSONResponse(
        status_code=422,
        content={"detail": translate_detail(jsonable_encoder(exc.errors()))},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last line of defence: an unexpected error must reach the customer as a
    readable Russian message, never as a bare "Internal Server Error" or a
    stack trace. Starlette still re-raises after this handler, so the failure
    is logged and reported to Sentry as usual."""
    return JSONResponse(
        status_code=500,
        content={"detail": translate("Внутренняя ошибка сервера. Мы уже разбираемся — попробуйте позже.")},
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {
        "name": settings.project_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "message": "Novex backend is running.",
    }
