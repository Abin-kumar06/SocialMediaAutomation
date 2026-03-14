"""
Services package.

This project originally shipped a single-module `app/services.py`.
To support a dedicated service module at `app/services/instagram_token_service.py`
without breaking existing imports (`from app.services import ImageService, ...`),
we dynamically load the legacy module and re-export its public service classes.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "services.py"


def _load_legacy_services() -> ModuleType:
    spec = spec_from_file_location("app._legacy_services", _LEGACY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load legacy services from {_LEGACY_PATH}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


_legacy: ModuleType = _load_legacy_services()

# Re-export legacy services for backwards compatibility
ImageService = getattr(_legacy, "ImageService")
InstagramService = getattr(_legacy, "InstagramService")

__all__ = [
    "ImageService",
    "InstagramService",
]

