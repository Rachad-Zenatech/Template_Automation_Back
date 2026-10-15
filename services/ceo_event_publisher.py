"""
Cross-application event publisher for CEO Dashboard integration.
Mirrors the pattern from Admin:
- Fire-and-forget non-blocking background HTTP events to CEO Dashboard (/api/v1/ceo/events)
- Allows CEO Dashboard to track travel bookings, events, rosters, and vehicle logistics in real-time
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 2.0


async def _send_event_async(event_type: str, source: str, entity_id: str, data: Dict[str, Any]):
    ceo_api_base = os.getenv("CEO_DASHBOARD_API_URL", os.getenv("CEO_API_BASE", "http://127.0.0.1:8005"))
    if not ceo_api_base:
        logger.debug("CEO_DASHBOARD_API_URL is not set; skipping event publishing")
        return
    url = f"{ceo_api_base.rstrip('/')}/api/v1/ceo/events"
    payload = {
        "event_type": event_type,
        "source": source,
        "entity_id": entity_id,
        "data": data,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"CEO event publish returned status {resp.status_code}")
    except Exception as exc:
        logger.debug(f"CEO event publish skipped (non-blocking): {exc}")


def publish_ceo_event(event_type: str, source: str = "template", entity_id: str = "", data: Optional[Dict[str, Any]] = None):
    """
    Fire-and-forget background task to publish cross-application events to the CEO Dashboard.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_send_event_async(event_type, source, entity_id, data or {}))
    except Exception as exc:
        logger.debug(f"Could not dispatch event {event_type}: {exc}")
