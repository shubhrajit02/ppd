"""Metadata-only logging; source code and provider responses are never logged."""

import json
import logging


def event(logger: logging.Logger, name: str, **fields: str | int | float) -> None:
    logger.info(json.dumps({"event": name, **fields}))
