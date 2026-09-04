"""
Community pool-buy service.

Tier discounts are computed server-side (the frontend only displays them):
    25%  → −4%
    50%  → −8%
    75%  → −12%
    100% → −18%

Pool progress = seeded volume (demo seed, clearly flagged `is_demo`) + real
`pool_joins` volume. Final pricing is always calculated here, never trusted
from the client.
"""

import random
from datetime import datetime, timedelta

from models import listing as listing_model
from models import pool as pool_model

POOL_TIERS = [
    (0, 0, "Base price"),
    (25, 4, "Early pool bonus"),
    (50, 8, "Half batch unlocked"),
    (75, 12, "Bulk rate unlocked"),
    (100, 18, "Full wholesale price"),
]

DEMO_NOTE = "Demo pool — seeded sample volume for illustration."


def pool_discount(pct_filled):
    disc, label = 0, "Base price"
    for threshold, d, lbl in POOL_TIERS:
        if pct_filled >= threshold:
            disc, label = d, lbl
    return disc, label


def next_tier(pct_filled):
    for threshold, d, lbl in POOL_TIERS:
        if pct_filled < threshold:
            return {"at_pct": threshold, "discount": d, "label": lbl}
    return None


def _stable_seed(key):
    return random.Random("pool-%s" % key)


def enrich_pool(p, joined_kg, members):
    current = int(p.get("seeded_kg") or 0) + int(joined_kg)
    target = int(p.get("target_kg") or 0)
    pct = min(100, round(current / target * 100)) if target else 0
    disc, label = pool_discount(pct)
    base = float(p.get("base_price") or 0)
    price_now = round(base * (1 - disc / 100), 2)

    try:
        ends = datetime.fromisoformat(p.get("ends_at"))
    except Exception:
        ends = datetime.now() + timedelta(hours=12)
    secs_left = max(0, int((ends - datetime.now()).total_seconds()))

    nt = next_tier(pct)
    kg_to_next = 0
    if nt:
        kg_to_next = max(0, int(target * nt["at_pct"] / 100) - current)

    return dict(p, **{
        "current_kg": current,
        "members": members,  # honest count (no fabricated +N)
        "pct": pct,
        "discount_pct": disc,
        "tier_label": label,
        "price_now": price_now,
        "base_price": base,
        "seconds_left": secs_left,
        "hours_left": round(secs_left / 3600, 1),
        "unlocked": pct >= 100,
        "next_tier": nt,
        "kg_to_next_tier": kg_to_next,
        "is_demo": bool(p.get("is_demo", 1)),
        "demo_note": DEMO_NOTE if p.get("is_demo", 1) else "",
        "tiers": [
            {"at_pct": t[0], "discount": t[1], "label": t[2],
             "price": round(base * (1 - t[1] / 100), 2)}
            for t in POOL_TIERS
        ],
    })


def get_pools():
    """Active pools with live (server-computed) pricing and progress."""
    seed_pools_if_needed()
    pools = pool_model.get_pools(status="open")
    out = []
    for p in pools:
        joined_kg, members = pool_model.pool_join_stats(p["id"])
        out.append(enrich_pool(p, joined_kg, members))
    return out


def seed_pools_if_needed():
    """
    Ensure the Community widget has content during demos.

    Pools are always created FROM real farmer listings (never from hardcoded
    products), but a `seeded_kg` demo volume is added so the progress bar shows
    movement without many real users. These pools are flagged `is_demo=1`.
    """
    if pool_model.count_open_pools() >= 3:
        return
    listings = listing_model.list_listings(where="status != 'inactive'", params=())
    for l in listings[:6]:
        if pool_model.get_open_pool_for_listing(l["id"]):
            continue
        rnd = _stable_seed(l["id"])
        target = rnd.choice([300, 500, 750, 1000])
        seeded = int(target * rnd.uniform(0.25, 0.72))
        ends = datetime.now() + timedelta(hours=rnd.randint(6, 36))
        pool_model.create_pool(
            crop_name=l.get("crop_name"),
            listing_id=l.get("id"),
            photo=l.get("image_url") or l.get("photo") or "",
            grade=l.get("grade", "A"),
            base_price=float(l.get("price_per_unit") or l.get("price") or 20),
            target_kg=target,
            seeded_kg=seeded,
            ends_at=ends.isoformat(),
            location=l.get("location", ""),
            farmer_name=l.get("farmer_name", ""),
            status="open",
            is_demo=1,
        )


def join_pool(pool_id, consumer_phone, consumer_name, org_name, qty_kg):
    pool = pool_model.get_pool(pool_id)
    if not pool:
        return None, "Pool not found"
    if pool.get("status") != "open":
        return None, "This pool is no longer open"
    pool_model.add_pool_join(pool_id, consumer_phone, consumer_name, org_name, qty_kg)
    joined_kg, members = pool_model.pool_join_stats(pool_id)
    return enrich_pool(pool, joined_kg, members), None


def price_after_pool_discount(listing_id, base_price):
    """Server-side unit price after applying the listing's open pool tier."""
    pool = pool_model.get_open_pool_for_listing(listing_id)
    if not pool:
        return round(float(base_price), 2), 0
    joined_kg, _members = pool_model.pool_join_stats(pool["id"])
    current = int(pool.get("seeded_kg") or 0) + int(joined_kg)
    target = int(pool.get("target_kg") or 0)
    pct = min(100, round(current / target * 100)) if target else 0
    disc, _label = pool_discount(pct)
    return round(float(base_price) * (1 - disc / 100), 2), disc
