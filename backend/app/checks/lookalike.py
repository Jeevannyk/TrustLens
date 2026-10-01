from typing import Optional

# Domains most impersonated in Indian phishing/smishing (banks, payments, gov, courier).
# Extend this list as you find more targets during demo prep.
KNOWN_BRAND_DOMAINS: dict[str, str] = {
    "sbi.co.in": "State Bank of India",
    "onlinesbi.sbi": "State Bank of India",
    "hdfcbank.com": "HDFC Bank",
    "icicibank.com": "ICICI Bank",
    "axisbank.com": "Axis Bank",
    "kotak.com": "Kotak Mahindra Bank",
    "paytm.com": "Paytm",
    "phonepe.com": "PhonePe",
    "gpay.google.com": "Google Pay",
    "indiapost.gov.in": "India Post",
    "ippbonline.com": "India Post Payments Bank",
    "irctc.co.in": "IRCTC",
    "incometax.gov.in": "Income Tax Department",
    "uidai.gov.in": "UIDAI / Aadhaar",
    "licindia.in": "LIC",
    "flipkart.com": "Flipkart",
    "amazon.in": "Amazon India",
    "airtel.in": "Airtel",
    "jio.com": "Jio",
}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def check_lookalike(domain: str, max_distance: int = 2) -> tuple[Optional[str], Optional[int]]:
    """Returns (matched_brand, edit_distance) for the closest known brand domain within
    max_distance, skipping an exact match (that's the real domain, not a lookalike)."""
    domain = domain.lower().strip()
    best_brand: Optional[str] = None
    best_dist: Optional[int] = None
    for brand_domain, brand_name in KNOWN_BRAND_DOMAINS.items():
        if domain == brand_domain:
            return None, None  # exact match to the real domain, not impersonation
        dist = _levenshtein(domain, brand_domain)
        if dist <= max_distance and (best_dist is None or dist < best_dist):
            best_brand, best_dist = brand_name, dist
    return best_brand, best_dist
