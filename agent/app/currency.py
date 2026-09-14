"""Currency conversion utilities for the Riverline financial assistant.

Fetches real-time exchange rates from Frankfurter (https://www.frankfurter.app),
a free, open-source API backed by ECB reference rates. No API key is required.

Design notes:
- Rates are cached in-memory keyed by (date, currency) for the process lifetime.
  A new day's rate is fetched automatically on the first call after midnight.
- All conversion functions are async to avoid blocking the Pipecat event loop.
- This module must NOT be imported by engine.py (engine.py is dependency-free).
  See AGENTS.md §2 for the module boundary rules.
"""

import logging
from datetime import datetime, timezone
from typing import Final

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FRANKFURTER_BASE: Final[str] = "https://api.frankfurter.app"

# Maps common spoken/informal currency names to ISO 4217 codes.
_CURRENCY_ALIASES: Final[dict[str, str]] = {
    "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD",
    "us dollar": "USD", "american dollar": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "sterling": "GBP",
    "british pound": "GBP", "£": "GBP",
    "dirham": "AED", "dirhams": "AED", "aed": "AED",
    "sgd": "SGD", "singapore dollar": "SGD",
    "cad": "CAD", "canadian dollar": "CAD",
    "aud": "AUD", "australian dollar": "AUD",
    "yen": "JPY", "jpy": "JPY", "¥": "JPY",
    "chf": "CHF", "franc": "CHF",
    "yuan": "CNY", "cny": "CNY", "rmb": "CNY",
    # INR aliases — no conversion needed
    "rupee": "INR", "rupees": "INR", "inr": "INR",
    "₹": "INR", "rs": "INR", "rs.": "INR",
}

# In-memory daily cache: (iso_date_str, currency_code) -> INR rate
_rate_cache: dict[tuple[str, str], float] = {}


def normalise_currency(raw: str) -> str:
    """Convert an informal currency name or symbol to an ISO 4217 code.

    Returns the uppercased input unchanged if no alias is found, so that
    unknown-but-valid ISO codes (e.g. 'MYR') pass through correctly.
    """
    return _CURRENCY_ALIASES.get(raw.strip().lower(), raw.strip().upper())


async def get_inr_rate(currency_code: str) -> float:
    """Return how many INR one unit of *currency_code* is worth today.

    Results are cached per calendar day (UTC) so the API is called at most
    once per currency per day within the same process.

    Raises:
        ValueError: If the currency code is unrecognised by Frankfurter.
        httpx.HTTPError: On network failure (caller should handle gracefully).
    """
    iso = normalise_currency(currency_code)
    if iso == "INR":
        return 1.0

    today_str = datetime.now(timezone.utc).date().isoformat()
    cache_key = (today_str, iso)

    if cache_key in _rate_cache:
        return _rate_cache[cache_key]

    url = f"{_FRANKFURTER_BASE}/latest"
    params = {"from": iso, "to": "INR"}

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    rates = data.get("rates", {})
    if "INR" not in rates:
        raise ValueError(
            f"Currency '{iso}' is not supported. "
            "Supported currencies include USD, EUR, GBP, AED, SGD, CAD, AUD, JPY, CHF, CNY."
        )

    rate = float(rates["INR"])
    _rate_cache[cache_key] = rate
    logger.info(f"Fetched exchange rate: 1 {iso} = {rate:.4f} INR (date: {today_str})")
    return rate


async def convert_to_inr(amount: float, currency_code: str) -> float:
    """Convert *amount* in *currency_code* to its INR equivalent.

    This is the single entry point for all currency conversions in the system.
    """
    rate = await get_inr_rate(currency_code)
    inr_amount = amount * rate
    logger.info(
        f"Currency conversion: {amount:.2f} {normalise_currency(currency_code)} "
        f"-> {inr_amount:.2f} INR (rate: {rate:.4f})"
    )
    return inr_amount
