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
    "paypal.com": "PayPal",
    "google.com": "Google",
    "microsoft.com": "Microsoft",
    "apple.com": "Apple",
    "whatsapp.com": "WhatsApp",
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


# Second-level suffixes under which people register domains (so "sbi.co.in" is the
# registrable domain, not "co.in"). Not a full public-suffix list; covers common cases.
_MULTI_PART_SUFFIXES = {
    "co.in", "gov.in", "org.in", "net.in", "ac.in", "nic.in",
    "co.uk", "org.uk", "gov.uk", "ac.uk",
    "com.au", "net.au", "org.au", "gov.au",
}


def _registrable_domain(host: str) -> str:
    """Returns eTLD+1 for host (e.g. accounts.google.com -> google.com, a.b.co.in -> b.co.in)."""
    labels = host.lower().strip().rstrip(".").split(".")
    keep = 3 if len(labels) >= 3 and ".".join(labels[-2:]) in _MULTI_PART_SUFFIXES else 2
    return ".".join(labels[-keep:])


# Subdomain entries (e.g. gpay.google.com) are covered by their parent's registrable domain.
_BRAND_REGISTRABLES: dict[str, str] = {
    d: name for d, name in KNOWN_BRAND_DOMAINS.items() if _registrable_domain(d) == d
}


def check_lookalike(domain: str) -> tuple[Optional[str], Optional[int]]:
    """Returns (matched_brand, edit_distance) for the closest known brand domain, comparing
    registrable domains. An exact registrable match (including any subdomain of it) is the
    real domain, not a lookalike. Allowed distance is 1 for brand labels under 10 chars,
    otherwise 2, to avoid false positives on short names."""
    registrable = _registrable_domain(domain)
    best_brand: Optional[str] = None
    best_dist: Optional[int] = None
    for brand_domain, brand_name in _BRAND_REGISTRABLES.items():
        if registrable == brand_domain:
            return None, None  # the real domain, not impersonation
        max_distance = 1 if len(brand_domain.split(".")[0]) < 10 else 2
        dist = _levenshtein(registrable, brand_domain)
        if dist <= max_distance and (best_dist is None or dist < best_dist):
            best_brand, best_dist = brand_name, dist
    return best_brand, best_dist
