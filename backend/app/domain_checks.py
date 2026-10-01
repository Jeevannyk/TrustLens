"""Runs the deterministic per-domain checks concurrently, each with its own timeout and
bounded retry, so one slow or failing lookup degrades to a note instead of failing the request."""
import asyncio
import ipaddress
import logging

import httpx

from .checks.domain_age import get_domain_info
from .checks.heuristics import skeleton, url_heuristics
from .checks.lookalike import check_lookalike, official_brand, registrable_domain
from .checks.safe_browsing import check_safe_browsing
from .schemas import DomainCheckResult
from .urls import ascii_host, host_of

logger = logging.getLogger(__name__)

MAX_DOMAINS = 10
CHECK_TIMEOUT_SECONDS = 8.0
CHECK_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.5

_AGE_UNAVAILABLE = "Domain age lookup unavailable"


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


async def _rdap(domain: str, client: httpx.AsyncClient) -> tuple[dict, str | None]:
    """RDAP with a per-attempt timeout and one bounded retry. Never raises."""
    error: str | None = _AGE_UNAVAILABLE
    for attempt in range(CHECK_ATTEMPTS):
        try:
            info, err = await asyncio.wait_for(get_domain_info(domain, client), CHECK_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - includes asyncio.TimeoutError
            logger.warning("rdap lookup failed for %s: %r", domain, exc)
            info, err = {}, _AGE_UNAVAILABLE
        if not err:
            return info, None
        if err == "rdap status 404":
            return {}, "No registration record found"
        logger.warning("rdap error for %s: %s", domain, err)
        error = _AGE_UNAVAILABLE
        if attempt + 1 < CHECK_ATTEMPTS:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * 2**attempt)
    return {}, error


async def _safe_browsing(urls: list[str], client: httpx.AsyncClient) -> dict[str, tuple[bool, str | None]]:
    try:
        return await asyncio.wait_for(check_safe_browsing(urls, client), CHECK_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe browsing check failed: %r", exc)
        return {}


async def run_domain_checks(urls: list[str]) -> list[DomainCheckResult]:
    if not urls:
        return []
    by_domain: dict[str, list[str]] = {}
    for u in urls:
        by_domain.setdefault(host_of(u), []).append(u)
    domains = sorted(by_domain)[:MAX_DOMAINS]

    def full(u: str) -> str:
        return u if "://" in u else f"http://{u}"

    sb_urls = [full(u) for d in domains for u in by_domain[d]]

    async with httpx.AsyncClient() as client:
        rdap_tasks = [
            _rdap(registrable_domain(ascii_host(d)), client) if not _is_ip(d) else asyncio.sleep(0, ({}, None))
            for d in domains
        ]
        results = await asyncio.gather(*rdap_tasks, _safe_browsing(sb_urls, client))
    rdap_results, sb_results = results[:-1], results[-1]

    checks: list[DomainCheckResult] = []
    for domain, (info, error) in zip(domains, rdap_results):
        ascii_d = ascii_host(domain)
        brand, distance = check_lookalike(ascii_d)
        if brand is None and ascii_d != domain:
            brand, distance = check_lookalike(skeleton(domain))
        heuristics = sorted({code for u in by_domain[domain] for code in url_heuristics(u)})
        sb_hit, sb_type = next(
            (sb_results[full(u)] for u in by_domain[domain] if sb_results.get(full(u), (False, None))[0]),
            (False, None),
        )
        age_days = info.get("age_days")
        checks.append(
            DomainCheckResult(
                domain=domain,
                age_days=age_days,
                is_new_domain=age_days is not None and age_days < 30,
                last_changed_days=info.get("last_changed_days"),
                expires_in_days=info.get("expires_in_days"),
                registrar=info.get("registrar"),
                domain_status=info.get("domain_status", []),
                nameservers=info.get("nameservers", []),
                heuristics=heuristics,
                lookalike_of=brand,
                lookalike_distance=distance,
                official_domain_of=None if _is_ip(domain) else official_brand(ascii_d),
                safe_browsing_hit=sb_hit,
                safe_browsing_threat_type=sb_type,
                error=error,
            )
        )
    return checks
