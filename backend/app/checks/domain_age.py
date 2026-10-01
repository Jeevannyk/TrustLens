from datetime import datetime, timezone
from typing import Optional

import httpx

RDAP_URL = "https://rdap.org/domain/{domain}"


async def get_domain_age_days(domain: str, client: httpx.AsyncClient) -> tuple[Optional[int], Optional[str]]:
    """Returns (age_in_days, error). None age with no error means RDAP had no registration event."""
    try:
        resp = await client.get(RDAP_URL.format(domain=domain), timeout=6.0)
        if resp.status_code != 200:
            return None, f"rdap status {resp.status_code}"
        data = resp.json()
        for event in data.get("events", []):
            if event.get("eventAction") == "registration":
                registered = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - registered).days
                return age, None
        return None, None
    except Exception as exc:  # noqa: BLE001 - surface as check error, not a crash
        return None, str(exc)
