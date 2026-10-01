from datetime import datetime, timezone

import httpx

RDAP_URL = "https://rdap.org/domain/{domain}"


def _registrar_name(data: dict) -> str | None:
    for entity in data.get("entities", []):
        roles = entity.get("roles")
        if not isinstance(roles, list) or "registrar" not in roles:
            continue
        vcard = entity.get("vcardArray")
        if vcard and len(vcard) > 1:
            for field in vcard[1]:
                if field[0] == "fn" and len(field) > 3 and isinstance(field[3], str):
                    return field[3]
        return entity.get("handle")
    return None


async def get_domain_info(domain: str, client: httpx.AsyncClient) -> tuple[dict, str | None]:
    """Returns (info, error). info may contain: age_days, last_changed_days,
    expires_in_days, registrar, domain_status, nameservers — whichever fields RDAP
    actually provided for this domain."""
    try:
        resp = await client.get(RDAP_URL.format(domain=domain), timeout=6.0, follow_redirects=True)
        if resp.status_code != 200:
            return {}, f"rdap status {resp.status_code}"
        data = resp.json()

        now = datetime.now(timezone.utc)
        info: dict = {}

        for event in data.get("events", []):
            try:
                when = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                action = event.get("eventAction")
                if action == "registration":
                    info["age_days"] = (now - when).days
                elif action == "last changed":
                    info["last_changed_days"] = (now - when).days
                elif action == "expiration":
                    info["expires_in_days"] = (when - now).days
            except (KeyError, AttributeError, TypeError, ValueError):
                continue  # one malformed event must not discard the others

        if data.get("status"):
            info["domain_status"] = data["status"]

        registrar = _registrar_name(data)
        if registrar:
            info["registrar"] = registrar

        nameservers = [ns.get("ldhName") for ns in data.get("nameservers", []) if ns.get("ldhName")]
        if nameservers:
            info["nameservers"] = nameservers

        return info, None
    except Exception as exc:  # noqa: BLE001 - surface as check error, not a crash
        return {}, str(exc)
