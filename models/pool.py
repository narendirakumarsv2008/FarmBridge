"""Pool model helper."""

TIERS = [
    (0, 0, 'Base price'),
    (25, 4, 'Early pool bonus'),
    (50, 8, 'Half batch unlocked'),
    (75, 12, 'Bulk rate unlocked'),
    (100, 18, 'Full wholesale price'),
]


def discount_for(pct):
    disc, label = 0, 'Base price'
    for threshold, d, lbl in TIERS:
        if pct >= threshold:
            disc, label = d, lbl
    return disc, label
