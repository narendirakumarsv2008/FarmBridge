"""
Database schema (portable across SQLite and MySQL).

Each table body uses placeholders:
  {pk}       → engine-specific auto-increment primary key
  {text}     → TEXT
  {longtext} → LONGTEXT (MySQL) / TEXT (SQLite)

`db.init_db()` formats these per engine and creates them with
`CREATE TABLE IF NOT EXISTS`. `database/migrations/` handles changes to
databases created by older versions of the app.
"""

SCHEMA = {
    "users": """(
        id         {pk},
        name       VARCHAR(120) NOT NULL,
        phone      VARCHAR(20) NOT NULL UNIQUE,
        email      VARCHAR(190),
        role       VARCHAR(40) DEFAULT 'consumer',
        created_at VARCHAR(40),
        updated_at VARCHAR(40)
    )""",

    "farmers": """(
        id         {pk},
        user_id    INTEGER,
        farm_name  VARCHAR(190),
        location   VARCHAR(255),
        city       VARCHAR(120),
        state      VARCHAR(120),
        pincode    VARCHAR(12),
        latitude   DOUBLE,
        longitude  DOUBLE,
        created_at VARCHAR(40),
        updated_at VARCHAR(40)
    )""",

    "consumers": """(
        id                {pk},
        user_id           INTEGER,
        phone             VARCHAR(20) NOT NULL UNIQUE,
        name              VARCHAR(120),
        email             VARCHAR(190),
        consumer_type     VARCHAR(20),
        delivery_address  {text},
        landmark          VARCHAR(190),
        organization_name VARCHAR(190),
        city              VARCHAR(120),
        state             VARCHAR(120),
        pincode           VARCHAR(12),
        latitude          DOUBLE,
        longitude         DOUBLE,
        created_at        VARCHAR(40),
        updated_at        VARCHAR(40)
    )""",

    "listings": """(
        id                 {pk},
        farmer_id          INTEGER,
        farmer_name        VARCHAR(120),
        phone              VARCHAR(20),
        crop_name          VARCHAR(120),
        harvest_date       VARCHAR(40),
        quantity           VARCHAR(40),
        quantity_total     INTEGER,
        quantity_available INTEGER,
        unit               VARCHAR(20),
        price              DOUBLE,
        price_per_unit     DOUBLE,
        location           VARCHAR(255),
        city               VARCHAR(120),
        image_url          VARCHAR(500),
        photo              {longtext},
        grade              VARCHAR(4),
        freshness_score    INTEGER,
        expiry_date        VARCHAR(40),
        shelf_life         INTEGER,
        mandi_price        DOUBLE,
        platform_price     DOUBLE,
        mandi_name         VARCHAR(255),
        status             VARCHAR(40),
        voice_transcript   {text},
        sold_kg            INTEGER DEFAULT 0,
        created_at         VARCHAR(40),
        updated_at         VARCHAR(40)
    )""",

    "orders": """(
        id             {pk},
        order_code     VARCHAR(40),
        consumer_phone VARCHAR(20),
        consumer_name  VARCHAR(120),
        consumer_type  VARCHAR(20),
        subtotal       DOUBLE,
        delivery_fee   DOUBLE,
        discount       DOUBLE,
        total          DOUBLE,
        payment_method VARCHAR(40),
        payment_status VARCHAR(40),
        status         VARCHAR(40),
        address        {text},
        eta_minutes    INTEGER,
        source         VARCHAR(40),
        created_at     VARCHAR(40),
        updated_at     VARCHAR(40)
    )""",

    "order_items": """(
        id                {pk},
        order_id          INTEGER,
        listing_id        INTEGER,
        crop_name_snapshot VARCHAR(120),
        quantity          INTEGER,
        price_per_unit    DOUBLE,
        subtotal          DOUBLE,
        farmer_id         INTEGER,
        farmer_phone      VARCHAR(20),
        created_at        VARCHAR(40)
    )""",

    "pools": """(
        id          {pk},
        crop_name   VARCHAR(120),
        listing_id  INTEGER,
        photo       {longtext},
        grade       VARCHAR(4),
        base_price  DOUBLE,
        target_kg   INTEGER,
        seeded_kg   INTEGER,
        ends_at     VARCHAR(40),
        location    VARCHAR(255),
        farmer_name VARCHAR(120),
        status      VARCHAR(20),
        is_demo     INTEGER DEFAULT 1,
        created_at  VARCHAR(40)
    )""",

    "pool_joins": """(
        id             {pk},
        pool_id        INTEGER,
        consumer_phone VARCHAR(20),
        consumer_name  VARCHAR(120),
        org_name       VARCHAR(190),
        qty_kg         INTEGER,
        joined_at      VARCHAR(40)
    )""",

    "subscriptions": """(
        id             {pk},
        consumer_phone VARCHAR(20),
        consumer_name  VARCHAR(120),
        org_name       VARCHAR(190),
        crop_name      VARCHAR(120),
        listing_id     INTEGER,
        qty_kg         INTEGER,
        price_per_kg   DOUBLE,
        frequency      VARCHAR(40),
        weekdays       VARCHAR(190),
        time_slot      VARCHAR(60),
        start_date     VARCHAR(40),
        end_date       VARCHAR(40),
        active         INTEGER DEFAULT 1,
        status         VARCHAR(20) DEFAULT 'active',
        created_at     VARCHAR(40),
        updated_at     VARCHAR(40)
    )""",

    "delivery_tracking": """(
        id         {pk},
        order_id   INTEGER,
        status     VARCHAR(40),
        note       VARCHAR(255),
        latitude   DOUBLE,
        longitude  DOUBLE,
        created_at VARCHAR(40),
        updated_at VARCHAR(40)
    )""",

    "schema_migrations": """(
        id          {pk},
        version     INTEGER,
        description VARCHAR(190),
        applied_at  VARCHAR(40)
    )""",
}

# Listing lifecycle statuses.
LISTING_STATUSES = ("active", "low_stock", "sold_out", "expired", "inactive")

# Order lifecycle statuses (canonical, stored in DB).
ORDER_STATUSES = (
    "ORDER_PLACED",
    "FARMER_CONFIRMED",
    "HARVEST_PACKED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "CANCELLED",
)

# Human-friendly labels, returned to the frontend alongside the canonical code.
ORDER_STATUS_LABELS = {
    "ORDER_PLACED": "Order Placed",
    "FARMER_CONFIRMED": "Farmer Confirmed",
    "HARVEST_PACKED": "Harvest Packed",
    "OUT_FOR_DELIVERY": "Out for Delivery",
    "DELIVERED": "Delivered",
    "CANCELLED": "Cancelled",
}

# Valid transitions. A status can only move to one of the listed successors.
ORDER_TRANSITIONS = {
    "ORDER_PLACED": {"FARMER_CONFIRMED", "CANCELLED"},
    "FARMER_CONFIRMED": {"HARVEST_PACKED", "CANCELLED"},
    "HARVEST_PACKED": {"OUT_FOR_DELIVERY", "CANCELLED"},
    "OUT_FOR_DELIVERY": {"DELIVERED", "CANCELLED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}

# Linear forward flow (used for the progress bar / legacy "advance" endpoint).
ORDER_FLOW = [
    "ORDER_PLACED",
    "FARMER_CONFIRMED",
    "HARVEST_PACKED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
]
