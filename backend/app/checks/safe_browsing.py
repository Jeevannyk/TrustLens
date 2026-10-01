import os
from typing import Optional

import httpx

SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"


async def check_safe_browsing(
    urls: list[str], client: httpx.AsyncClient
) -> Optional[dict[str, tuple[bool, Optional[str]]]]:
    """Returns {url: (is_threat, threat_type)}, or None if the check did not run
    (no API key configured, or the request failed)."""
    api_key = os.environ.get("GOOGLE_SAFE_BROWSING_API_KEY")
    if not api_key:
        return None
    if not urls:
        return {}

    body = {
        "client": {"clientId": "trustlens", "clientVersion": "0.1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": u} for u in urls],
        },
    }
    result: dict[str, tuple[bool, Optional[str]]] = {url: (False, None) for url in urls}
    try:
        resp = await client.post(SAFE_BROWSING_URL, params={"key": api_key}, json=body, timeout=6.0)
        resp.raise_for_status()
        for match in resp.json().get("matches", []):
            threatened_url = match.get("threat", {}).get("url")
            threat_type = match.get("threatType")
            if threatened_url in result:
                result[threatened_url] = (True, threat_type)
    except Exception:  # noqa: BLE001 - a failed check should not crash the whole report
        return None
    return result
