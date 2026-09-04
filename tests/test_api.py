"""End-to-end API tests (SQLite development mode)."""

import json

from conftest import make_listing


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_auth_login_returns_token_and_user(client):
    res = client.post("/api/auth/login", json={"name": "Ramesh Kumar", "phone": "9876543210"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["token"]
    assert body["data"]["user"]["phone"] == "9876543210"


def test_auth_login_rejects_invalid_phone(client):
    res = client.post("/api/auth/login", json={"name": "Ramesh", "phone": "123"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_auth_me_with_token(client):
    token = client.post("/api/auth/login", json={"name": "Ramesh", "phone": "9876543210"}).get_json()["data"]["token"]
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token})
    assert res.status_code == 200
    assert res.get_json()["data"]["name"] == "Ramesh"


def test_legacy_login_alias_still_works(client):
    res = client.post("/api/login", json={"name": "Ramesh", "phone": "9876543210"})
    assert res.status_code == 200
    assert res.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------

def test_create_listing(client):
    res = make_listing(client)
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    assert body["grade_info"]["grade"] == "A"
    assert body["quantity_kg"] == 100
    assert body["quantity_available"] == 100


def test_create_listing_rejects_missing_field(client):
    res = client.post("/api/listings", json={"crop_name": "Tomato"})
    assert res.status_code == 400


def test_list_listings(client):
    make_listing(client)
    res = client.get("/api/listings")
    data = res.get_json()
    assert isinstance(data, list)
    assert data[0]["crop_name"] == "Tomato"
    assert data[0]["quantity_total"] == 100


# ---------------------------------------------------------------------------
# Marketplace (shared source of truth)
# ---------------------------------------------------------------------------

def test_market_shows_exact_farmer_data(client):
    make_listing(client)
    res = client.get("/api/market")
    body = res.get_json()
    item = body["items"][0]
    assert item["crop_name"] == "Tomato"
    assert item["available_kg"] == 100
    assert item["total_kg"] == 100
    assert item["live_price"] == 40.0  # no fabricated drift
    assert item["price_change_pct"] == 0.0
    assert item["sold_out"] is False
    assert body["source"] == "database"


# ---------------------------------------------------------------------------
# Orders + stock protection
# ---------------------------------------------------------------------------

def _order(client, qty, phone="9000000001"):
    return client.post("/api/orders", json={
        "items": [{"listing_id": 1, "qty": qty}],
        "consumer_phone": phone,
        "consumer_name": "Consumer B",
        "consumer_type": "individual",
        "address": "MG Road, Kochi",
    })


def test_create_order_reduces_stock(client):
    make_listing(client)
    res = _order(client, 5)
    assert res.status_code == 201
    body = res.get_json()
    assert body["subtotal"] == 200.0  # computed server-side (40 × 5)
    assert body["total"] == 225.0  # + 25 delivery fee

    market = client.get("/api/market").get_json()["items"][0]
    assert market["available_kg"] == 95


def test_overselling_is_prevented(client):
    make_listing(client)
    assert _order(client, 5).status_code == 201
    res = _order(client, 96, phone="9000000002")
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "INSUFFICIENT_STOCK"
    # stock unchanged (still 95)
    market = client.get("/api/market").get_json()["items"][0]
    assert market["available_kg"] == 95


def test_exact_remaining_stock_can_be_bought(client):
    make_listing(client)
    assert _order(client, 100).status_code == 201
    market = client.get("/api/market").get_json()["items"][0]
    assert market["available_kg"] == 0
    assert market["sold_out"] is True


def test_order_items_are_persisted(client):
    make_listing(client)
    _order(client, 5)
    orders = client.get("/api/orders?phone=9000000001").get_json()
    item = orders[0]["items"][0]
    assert item["crop_name"] == "Tomato"
    assert item["qty"] == 5
    assert item["price"] == 40.0


def test_frontend_price_is_ignored(client):
    """A client can't choose their own price — the DB price wins."""
    make_listing(client)
    res = client.post("/api/orders", json={
        "items": [{"listing_id": 1, "qty": 5, "price": 1.0}],  # bogus price
        "consumer_phone": "9000000001",
    })
    assert res.status_code == 201
    assert res.get_json()["subtotal"] == 200.0  # not 5.0


# ---------------------------------------------------------------------------
# Order status flow
# ---------------------------------------------------------------------------

def test_order_status_transitions(client, farmer):
    make_listing(client)
    _order(client, 5)
    token = farmer["token"]
    # invalid jump → 409
    res = client.put("/api/orders/1/status", json={"status": "DELIVERED"},
                     headers={"Authorization": "Bearer " + token})
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "INVALID_TRANSITION"
    # valid step
    res = client.put("/api/orders/1/status", json={"status": "FARMER_CONFIRMED"},
                     headers={"Authorization": "Bearer " + token})
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "FARMER_CONFIRMED"


def test_cancelled_order_restores_stock(client, farmer):
    make_listing(client)
    _order(client, 10)
    token = farmer["token"]
    res = client.put("/api/orders/1/status", json={"status": "CANCELLED"},
                     headers={"Authorization": "Bearer " + token})
    assert res.status_code == 200
    market = client.get("/api/market").get_json()["items"][0]
    assert market["available_kg"] == 100


# ---------------------------------------------------------------------------
# Ownership / authorization
# ---------------------------------------------------------------------------

def test_other_user_cannot_edit_listing(client, farmer):
    make_listing(client)
    other = client.post("/api/auth/login", json={"name": "Other", "phone": "9111111111"}).get_json()["data"]
    res = client.put("/api/listings/1", json={"price": 1},
                     headers={"Authorization": "Bearer " + other["token"]})
    assert res.status_code == 403


def test_unauthenticated_cannot_edit_listing(client):
    """No token + no registered phone ⇒ an anonymous caller can't mutate a listing."""
    make_listing(client)
    res = client.put("/api/listings/1", json={"price": 1, "phone": "9111111111"})
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "AUTH_REQUIRED"
    # and with no identity at all
    res = client.put("/api/listings/1", json={"price": 1})
    assert res.status_code == 401


def test_unauthenticated_cannot_delete_listing(client):
    make_listing(client)
    res = client.delete("/api/listings/1", json={"phone": "9111111111"})
    assert res.status_code == 401


def test_farmer_orders_lists_own_orders(client, farmer):
    make_listing(client)
    _order(client, 7)
    res = client.get("/api/farmer/orders?phone=9876543210",
                     headers={"Authorization": "Bearer " + farmer["token"]})
    assert res.status_code == 200
    orders = res.get_json()["data"]
    assert len(orders) == 1
    assert orders[0]["my_items"][0]["qty"] == 7


# ---------------------------------------------------------------------------
# Consumer profile (incl. deprecated alias)
# ---------------------------------------------------------------------------

def test_consumer_profile_upsert_and_get(client):
    payload = {
        "name": "Consumer B", "phone": "9000000001", "email": "b@example.com",
        "address": "MG Road, Kochi 682001", "consumer_type": "individual",
    }
    res = client.post("/api/consumer/profile", json=payload)
    assert res.status_code == 200
    assert res.get_json()["data"]["profile"]["consumer_type"] == "individual"

    res = client.get("/api/buyer/profile?phone=9000000001")  # legacy alias
    assert res.get_json()["data"]["found"] is True


# ---------------------------------------------------------------------------
# Pools + subscriptions
# ---------------------------------------------------------------------------

def test_pool_join(client):
    make_listing(client)
    client.get("/api/pools")  # seeds pools from real listings
    res = client.post("/api/pools/1/join", json={
        "qty_kg": 50, "consumer_phone": "9000000001", "consumer_name": "Consumer B",
    })
    assert res.status_code == 200
    pool = res.get_json()["data"]["pool"]
    assert pool["current_kg"] >= 50


def test_subscription_and_calendar(client):
    make_listing(client)
    res = client.post("/api/subscriptions", json={
        "consumer_phone": "9000000001", "consumer_name": "Consumer B",
        "listing_id": 1, "qty_kg": 10, "frequency": "Weekly",
        "weekdays": ["Mon", "Wed"], "start_date": "2026-09-04",
    })
    assert res.status_code == 201
    # server-computed contract price: 40 × 0.93 = 37.2
    assert res.get_json()["data"]["price_per_kg"] == 37.2

    cal = client.get("/api/subscriptions/calendar?phone=9000000001&days=30").get_json()
    assert cal["delivery_count"] >= 1
    assert cal["total_kg"] >= 10


# ---------------------------------------------------------------------------
# Grading + mandi
# ---------------------------------------------------------------------------

def test_grading_service():
    from services.grading_service import calculate_grade
    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    result = calculate_grade("Tomato", yesterday)
    assert result["grade"] == "A"
    assert result["freshness_score"] >= 70
    old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    assert calculate_grade("Tomato", old)["grade"] == "C"


def test_mandi_quote_is_demo_labeled(client):
    res = client.get("/api/mandi-price?crop=tomato")
    body = res.get_json()
    assert body["is_live"] is False
    assert "Demo" in body["source"] or "sample" in body["mandi_name"].lower()
    assert body["disclaimer"]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def test_database_tables_exist():
    from database.db import get_conn, table_exists
    conn = get_conn()
    for t in ("users", "farmers", "consumers", "listings", "orders",
              "order_items", "pools", "pool_joins", "subscriptions",
              "delivery_tracking", "schema_migrations"):
        assert table_exists(conn, t), "missing table %s" % t
    conn.close()


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "ok"
