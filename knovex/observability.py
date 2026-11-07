"""
Knovex AI - Enterprise Observability & Logging Module
Provides:
1. Context-aware structured logging (Request ID, Tenant ID)
2. FastAPI Request Logging Middleware with timing and X-Request-ID propagation
3. Centralized LangSmith Observability & Tracing for LangGraph & LLMs
"""

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variables for asynchronous request tracking
request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id_ctx", default="")


# ==============================================================================
# 1. Custom Log Formatter (Structured & Context-Aware)
# ==============================================================================
class KnovexLogFormatter(logging.Formatter):
    """
    Standard production formatter that attaches Request ID and Tenant ID to every log line.
    Supports both human-readable standard format and machine-readable JSON.
    """

    def __init__(self, json_mode: bool = False):
        super().__init__()
        self.json_mode = json_mode

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get("")
        t_id = tenant_id_ctx.get("")

        # Format ISO timestamp
        created_time = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        if self.json_mode:
            log_obj = {
                "timestamp": created_time,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": req_id or None,
                "tenant_id": t_id or None,
                "module": record.module,
                "line": record.lineno,
            }
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_obj)

        # Clean standard format
        context_parts = []
        if req_id:
            context_parts.append(f"req:{req_id[:8]}")
        if t_id:
            context_parts.append(f"tenant:{t_id[:8]}")

        ctx_str = f" [{' '.join(context_parts)}]" if context_parts else ""
        base_msg = f"{created_time} [{record.levelname:<5}] [{record.name}]{ctx_str} {record.getMessage()}"

        if record.exc_info:
            base_msg += "\n" + self.formatException(record.exc_info)
        return base_msg


# ==============================================================================
# 2. Observability Setup & Initialization
# ==============================================================================
def setup_logging(level: str = "INFO", json_mode: bool = False) -> None:
    """Configures application-wide logging with the KnovexLogFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing default handlers to avoid duplicate log outputs
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KnovexLogFormatter(json_mode=json_mode))
    root_logger.addHandler(handler)

    # Silence overly verbose external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)


def init_langsmith(
    tracing_enabled: bool,
    api_key: Optional[str],
    project: str = "knovex-ai",
    endpoint: str = "https://api.smith.langchain.com",
) -> bool:
    """
    Initializes LangSmith tracing by safely synchronizing environment variables
    for the native LangChain/LangGraph runtime.
    """
    logger = logging.getLogger("knovex.observability")

    if tracing_enabled and api_key and api_key.strip():
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key.strip()
        os.environ["LANGCHAIN_PROJECT"] = project.strip()
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint.strip()
        logger.info(f"LangSmith Observability ACTIVE -> Project: '{project}', Endpoint: '{endpoint}'")
        return True
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("LangSmith Observability is INACTIVE (Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY to enable)")
        return False


def get_langsmith_config(
    tenant_id: str,
    run_name: str,
    mode: str = "sync",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Standard factory for generating consistent LangGraph & LangChain execution configs.
    Tags each run with tenant isolation identifiers and current request tracing context.
    """
    req_id = request_id_ctx.get("")
    metadata: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "mode": mode,
        "app": "knovex-ai",
    }
    if req_id:
        metadata["request_id"] = req_id
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "tags": [f"tenant:{tenant_id}", f"mode:{mode}"],
        "metadata": metadata,
        "run_name": run_name,
    }


# ==============================================================================
# 3. FastAPI Request Logging & Tracing Middleware
# ==============================================================================
class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Captures X-Request-ID, tracks tenant context from authorization tokens,
    measures request execution latency, and logs structured access logs.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate unique Request ID
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token_req = request_id_ctx.set(req_id)

        # Attempt safe tenant extraction from JWT without blowing up if invalid/unauthenticated
        tenant_id = ""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
            try:
                import jwt
                from knovex.config import get_settings
                settings = get_settings()
                payload = jwt.decode(
                    raw_token,
                    settings.SECRET_KEY,
                    algorithms=[settings.ALGORITHM],
                    options={"verify_exp": False},
                )
                tenant_id = payload.get("tenant_id", "")
            except Exception:
                pass

        token_tenant = tenant_id_ctx.set(tenant_id)
        start_time = time.perf_counter()
        logger = logging.getLogger("knovex.access")

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Exclude noisy polling / static file routes from verbose logs
            path = request.url.path
            is_health_or_static = path in ("/health", "/api/v1/health") or path.startswith("/assets")

            if not is_health_or_static:
                logger.info(
                    f"{request.method} {path} -> {response.status_code} ({elapsed_ms:.1f}ms)"
                )

            # Propagate Request ID back to client in response headers
            response.headers["X-Request-ID"] = req_id
            return response

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                f"Unhandled Exception on {request.method} {request.url.path} ({elapsed_ms:.1f}ms): {exc}"
            )
            raise exc

        finally:
            request_id_ctx.reset(token_req)
            tenant_id_ctx.reset(token_tenant)
