"""
Live Mandi Comparison service.

The current provider is a MOCK: a static benchmark table clearly labeled
"Demo Market Benchmark". It is NOT live eNAM / Agmarknet data — we never claim
that. The provider interface makes it easy to swap in a real data source
(eNAM, Agmarknet, or any market-data vendor) later without touching routes.
"""

import logging

log = logging.getLogger("farmbridge.mandi")

# Demo benchmark table (₹/Kg, per crop). Clearly sample/demo data.
_DEMO_BENCHMARKS = {
    "tomato": {"price": 22, "mandi": "Azadpur (Delhi) — sample"},
    "potato": {"price": 18, "mandi": "Agra (UP) — sample"},
    "onion": {"price": 28, "mandi": "Lasalgaon (MH) — sample"},
    "wheat": {"price": 24, "mandi": "Karnal (HR) — sample"},
    "rice": {"price": 35, "mandi": "Karnal (HR) — sample"},
    "mango": {"price": 60, "mandi": "Vashi (MH) — sample"},
    "banana": {"price": 25, "mandi": "Jalgaon (MH) — sample"},
    "cabbage": {"price": 15, "mandi": "Bangalore APMC — sample"},
    "cauliflower": {"price": 20, "mandi": "Kolkata — sample"},
    "brinjal": {"price": 26, "mandi": "Chennai Koyambedu — sample"},
    "carrot": {"price": 30, "mandi": "Ooty (TN) — sample"},
    "chilli": {"price": 45, "mandi": "Guntur (AP) — sample"},
    "grapes": {"price": 55, "mandi": "Nashik (MH) — sample"},
}

DEFAULT_BENCHMARK_PRICE = 30


class MandiProvider:
    """Interface for a market-price provider."""

    def get_price(self, crop, location=None):
        raise NotImplementedError


class MockMandiProvider(MandiProvider):
    """Static demo benchmark provider (clearly labeled as sample data)."""

    name = "Demo Market Benchmark"

    def get_price(self, crop, location=None):
        crop = (crop or "").lower().strip()
        for k, v in _DEMO_BENCHMARKS.items():
            if k in crop or crop in k:
                return {
                    "price": v["price"],
                    "mandi": v["mandi"],
                    "trend": "sample",
                }
        loc = (location or "Local Mandi")[:30]
        return {
            "price": DEFAULT_BENCHMARK_PRICE,
            "mandi": "Nearest APMC — %s (sample)" % loc,
            "trend": "sample",
        }


# Example future providers (stubs — the architecture is ready).
class ENAMProvider(MandiProvider):
    """TODO: integrate the real eNAM / Agmarknet API here."""

    def get_price(self, crop, location=None):
        raise NotImplementedError("Real eNAM provider not configured yet")


_provider = MockMandiProvider()


def set_provider(provider):
    """Swap the active provider (used by tests / future integrations)."""
    global _provider
    _provider = provider


def get_mandi_quote(crop, location=None, farmer_price=None):
    """
    Return a comparison quote for a crop.

    Response keeps the frontend's expected keys (mandi_price, mandi_name,
    mandi_trend, platform_price, uplift_percent, extra_earning_*, comparison)
    and adds honest `source` / `is_live` / `disclaimer` metadata.
    """
    from services.grading_service import extract_crop_name_smart

    smart = extract_crop_name_smart(crop)
    if smart:
        crop = smart

    info = _provider.get_price(crop, location)
    benchmark = float(info["price"])

    # The "platform price" a farmer could expect: if they already set an asking
    # price we use it; otherwise we show an ESTIMATED direct price (benchmark
    # + a fixed 18% uplift) — clearly an estimate, not a promise.
    if farmer_price:
        platform_price = float(farmer_price)
        uplift_pct = round((platform_price - benchmark) / benchmark * 100, 1) if benchmark else 0.0
    else:
        uplift_pct = 18.0
        platform_price = round(benchmark * (1 + uplift_pct / 100), 2)

    return {
        "crop": crop,
        "mandi_price": benchmark,
        "mandi_name": info["mandi"],
        "mandi_trend": info["trend"],
        "platform_price": platform_price,
        "uplift_percent": round(uplift_pct, 1),
        "extra_earning_per_kg": round(max(0.0, platform_price - benchmark), 2),
        "extra_earning_per_quintal": round(max(0.0, (platform_price - benchmark) * 100), 2),
        "comparison": {"mandi": benchmark, "platform": platform_price},
        "source": getattr(_provider, "name", "mock"),
        "is_live": False,
        "disclaimer": "Demo Market Benchmark — sample data, not live eNAM prices.",
    }
