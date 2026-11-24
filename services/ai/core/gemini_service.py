import os
import asyncio
import logging
from typing import Any, Optional, List
from google import genai
from google.genai import errors

logger = logging.getLogger(__name__)

def _normalize_ai_model_name(name: str) -> str:
    """
    Normalizes a model name from the environment variable list
    into the format expected by the Google GenAI SDK.
    E.g. "Gemini 2.5 Flash" -> "gemini-2.5-flash"
    """
    return name.strip().lower().replace(" ", "-")
DEPRECATED_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-pro",
    "gemini-2.0-flash-lite",
    "gemini-2-flash",
    "gemini-2-flash-lite",
    "gemini-2",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
    "gemini-2.5-pro",
    # Google answers these with 404 ("no longer available to new users"); trying them only wastes a call and a wait.
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
}

_ROTATABLE_MESSAGES = (
    "404", "not found", "no longer available", "not available",
    "429", "503", "504", "resource_exhausted", "quota exceeded",
    "too many requests", "unavailable", "high demand", "deadline_exceeded",
    "deadline expired", "timed out", "is not supported", "invalid model", "deprecated",
)


def without_retired(models):
    """Return models that are not retired, preserving order (or original list if all are retired)."""
    kept = [m for m in models if m.strip().lower() not in DEPRECATED_MODELS]
    return kept or list(models)


def get_gemini_fallback_models() -> List[str]:
    """
    Retrieves and normalizes the list of available Gemini models
    from the environment configuration, filtering out deprecated/retired models.
    Guarantees active, proven general-purpose models are prioritized at the front of the rotation chain.
    """
    models_str = os.getenv("GEMINI_AVAILABLE_MODELS", "gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.1-pro-preview")
    raw_models = [_normalize_ai_model_name(m) for m in models_str.split(",") if m.strip()]

    # Filter out deprecated models that are no longer available in the Google GenAI API
    models = [m for m in raw_models if m not in DEPRECATED_MODELS]
    priority_order = ["gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview"]
    ordered = [m for m in priority_order if m in models]
    for m in models:
        if m not in ordered:
            ordered.append(m)
    return ordered or ["gemini-3-flash-preview", "gemini-3.1-flash-lite"]

def is_rotatable_model_error(e: Exception) -> bool:
    """
    Determines if a given exception represents a rate limit, quota exhaustion,
    temporary service spike, timeout, or deprecated/unavailable model (404 / 503 / 504 / 429).
    """
    try:
        from botocore.exceptions import ClientError
        if isinstance(e, ClientError):
            code = e.response.get("Error", {}).get("Code", "")
            if code in (
                "ThrottlingException",
                "ModelNotReadyException",
                "TooManyRequestsException",
                "ServiceUnavailableException",
                "AccessDeniedException",
                "ValidationException",
                "ResourceNotFoundException",
            ):
                return True
    except ImportError:
        pass
    if isinstance(e, errors.APIError):
        code = getattr(e, "code", getattr(e, "status", None))
        if code in (400, 404, 429, 503, 504):
            return True

    # A model that stopped answering (the request's timeout ran out): try the next one.
    # (google-genai raises its own httpx timeouts, so match by name).
    if isinstance(e, TimeoutError) or "Timeout" in type(e).__name__:
        return True

    msg = str(e).lower()
    return any(k in msg for k in _ROTATABLE_MESSAGES)

# Backward compatibility alias
is_quota_error = is_rotatable_model_error

import time

_model_cooldowns: dict[str, float] = {}


def _model_failure_cooldown_seconds(error: Exception) -> int:
    """Avoid retrying a model known to be unavailable while a request burst is in progress."""
    status_code = str(getattr(error, "code", "") or getattr(error, "status_code", ""))
    message = f"{status_code} {error}".lower()
    if any(part in message for part in ("404", "not found", "not available", "resourcenotfound", "accessdenied")):
        return 300
    if any(part in message for part in (
        "429", "500", "503", "504", "resource_exhausted", "quota", "high demand", "deadline",
        "throttl", "too many requests", "toomanyrequests", "serviceunavailable", "modelnotready",
    )):
        return 60
    if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.lower() or "timed out" in message:
        return 30
    if is_rotatable_model_error(error):
        return 60
    return 0


def model_is_available(model_name: str) -> bool:
    """Return false while a short provider-failure cooldown for this model is active."""
    until = _model_cooldowns.get(model_name)
    if until is None:
        return True
    if until > time.monotonic():
        return False
    _model_cooldowns.pop(model_name, None)
    return True


def record_model_failure(model_name: str, error: Exception) -> None:
    cooldown = _model_failure_cooldown_seconds(error)
    if cooldown:
        _model_cooldowns[model_name] = time.monotonic() + cooldown


async def generate_content_with_fallback(
    client: genai.Client,
    contents: Any,
    config: Optional[Any] = None,
) -> Any:
    """
    A robust wrapper around client.models.generate_content that automatically
    rotates through configured Gemini models upon encountering quota limits (429),
    server spikes (503), or deprecated/unavailable models (404).
    """
    models = get_gemini_fallback_models()

    last_exception = None

    for i, model_name in enumerate(models):
        logger.info(f"Attempting Gemini model: {model_name}")

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=contents,
                config=config,
            )

            if i > 0:
                logger.info(f"Gemini fallback succeeded with model: {model_name}")

            return response

        except Exception as e:
            last_exception = e
            if is_rotatable_model_error(e):
                record_model_failure(model_name, e)
                logger.warning(f"Gemini model {model_name} unavailable or quota exceeded ({e}). Moving to next model.")
                continue
            else:
                # Non-rotatable fatal error, re-raise immediately
                raise e

    print("no quota")
    logger.error("no quota")
    raise RuntimeError("no quota")
