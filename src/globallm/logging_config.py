"""Logging configuration for GlobalLM."""

import logging
import os
import sys
from datetime import datetime
from typing import Any

import structlog

from globallm.version import GIT_COMMIT


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog for the application.

    Args:
        level: Logging level (default: INFO)
    """
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create logs directory
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(level)

    # File handler - always at DEBUG level
    log_filename = datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + f"-{os.getpid()}.log"
    log_path = os.path.join(logs_dir, log_filename)
    file_handler = logging.FileHandler(log_path)
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=False),
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(
        logging.DEBUG
    )  # Root must be DEBUG to allow file handler to capture everything

    # Silence noisy loggers
    logging.getLogger("github").setLevel(logging.WARNING)

    # Log git commit once at startup
    logger = structlog.get_logger(__name__)
    logger.info("GlobalLM starting", git_commit=GIT_COMMIT or "unknown")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured structlog bound logger
    """
    return structlog.get_logger(name)
