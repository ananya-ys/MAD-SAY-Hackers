import logging
import sys
from contextvars import ContextVar
from uuid import UUID

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
repair_session_id_var: ContextVar[str] = ContextVar("repair_session_id", default="")


def add_correlation_id(logger, method: str, event_dict: EventDict) -> EventDict:
    cid = correlation_id_var.get()
    if cid:
        event_dict["correlation_id"] = cid
    sid = repair_session_id_var.get()
    if sid:
        event_dict["repair_session_id"] = sid
    return event_dict


def configure_logging() -> None:
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def set_repair_session_id(session_id: str | UUID) -> None:
    repair_session_id_var.set(str(session_id))
