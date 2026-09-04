# FARM BRIDGE — API Documentation

Base URL (local): `http://localhost:5000`

**Response conventions**

Most endpoints return an envelope:

```json
{ "success": true, "data": { ... } }
```

```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }
```

Error codes: `VALIDATION_ERROR`, `AUTH_REQUIRED`, `AUTH_INVALID`, `FORBIDDEN`,
`NOT_FOUND`, `CONFLICT`, `INSUFFICIENT_STOCK`, `INVALID_TRANSITION`,
`UPLOAD_ERROR`, `SERVER_ERROR`, `DB_ERROR`.

**Authentication**

Protected endpoints require `Authorization: Bearer <token>`. Get a token from
`POST /api/auth/login`. In development mode, requests that carry a valid
`phone` are also recognized (legacy frontend compatibility).

---

## Auth

### `POST /api/auth/login`  (alias: `POST /api/login`)

Log in with name + phone (+ optional OTP).

- **Auth:** none
- **Body:** `{ "name": "Ramesh Kumar", "phone": "9876543210", "otp": "123456"? }`

Development (no OTP): returns a token immediately (mock OTP included).

```json
{
  "success": true,
  "data": {
    "token": "<signed-token>",
    "user": { "id": 1, "name": "Ramesh Kumar", "phone": "9876543210", "role": "consumer" },
    "otp": "123456",
    "otp_required": false
  }
}
```

Production (no OTP): `{ "success": true, "data": { "otp_required": true, "otp_sent": true } }` (HTTP 202) — then verify.

- **Errors:** `400 VALIDATION_ERROR`, `401 AUTH_INVALID`, `503 AUTH_REQUIRED` (no SMS provider in production).

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ramesh Kumar","phone":"9876543210"}'
```

### `POST /api/auth/verify-otp`

- **Body:** `{ "phone": "9876543210", "otp": "123456" }`
- **Response:** `{ "success": true, "data": { "token": "...", "user": { ... } } }`
- **Errors:** `400`, `401 AUTH_INVALID`, `404`

### `GET /api/auth/me`

- **Auth:** Bearer token required.
- **Response:** `{ "success": true, "data": { "id", "name", "phone", "role" } }`

### `POST /api/auth/logout`

- **Response:** `{ "success": true, "data": { "logged_out": true } }` (stateless).

---

## Farmers

### `GET /api/farmer/profile`

- **Auth:** Bearer token.
- **Response:** `{ "success": true, "data": { "profile": { ... } } }`

### `PUT /api/farmer/profile`

- **Auth:** Bearer token.
- **Body:** `{ "farm_name", "location", "city", "state", "pincode", "latitude", "longitude" }`
- **Response:** updated profile.

### `GET /api/farmer/orders`

Orders involving the farmer's listings.

- **Auth:** Bearer token (or `?phone=` in development).
- **Params:** `phone`
- **Response:** `{ "success": true, "data": [ { order..., "items": [...], "my_items": [...] } ] }`

---

## Consumers

### `GET /api/consumer/profile?phone=...`  (alias: `GET /api/buyer/profile`)

- **Response:** `{ "success": true, "data": { "found": true, "profile": { ... } } }`

### `POST /api/consumer/profile`  (alias: `POST /api/buyer/profile`)

Create or update a consumer profile.

- **Body:** `{ "name", "phone", "email", "address"|"delivery_address", "consumer_type"|"buyer_type", "org_name"|"organization_name"?, "landmark"?, "city"?, "pincode"?, "latitude"?, "longitude"? }`
- **Response:** `{ "success": true, "data": { "profile": { ... } } }`

### `PUT /api/consumer/profile`

Partial update (requires the caller to own the profile).

---

## Listings

### `POST /api/listings`

Create a listing (farmer).

- **Body:**
```json
{
  "farmer_name": "Ramesh Kumar",
  "phone": "9876543210",
  "crop_name": "Tomato",
  "harvest_date": "2026-09-03",
  "quantity": "100",         // Kg (voice input like "5 quintal" is converted)
  "price": "40",             // ₹/Kg
  "location": "Kochi",
  "photo": "<base64 data URL>",   // optional
  "voice_transcript": "..."       // optional
}
```
- **Response (201):** `{ "success": true, "id", "grade_info", "mandi_price", "platform_price", "quantity_kg", "quantity_available", "image_url", "data": { ...same... } }`
- **Errors:** `400`, `403 FORBIDDEN` (listing for someone else's phone).

### `GET /api/listings`

All listings (array).

### `GET /api/listings/<id>`

Single listing. `{ "success": true, "data": { ... } }`

### `PUT /api/listings/<id>`

Update a listing (owner only). Accepts `crop_name`, `quantity`/`quantity_total`, `price`/`price_per_unit`, `location`, `city`, `status`, `photo`.

### `DELETE /api/listings/<id>`

Delete (owner only). `{ "success": true, "data": { "deleted": true } }`

### `PUT /api/listings/<id>/status`

Set listing status (owner only). `status ∈ active | low_stock | sold_out | expired | inactive`.

---

## Marketplace

### `GET /api/market`

The consumer marketplace — read directly from the shared database.

```json
{
  "items": [ { "id", "crop_name", "location", "farmer_name", "grade",
               "live_price", "available_kg", "total_kg", "stock_pct",
               "photo", "sold_out", "status", "freshness_label", "mandi_price",
               "savings_vs_mandi", "unit" } ],
  "count": 1,
  "updated_at": "2026-09-04T05:00:00",
  "source": "database"
}
```

- No mock products, no random price/stock drift — this is the exact data farmers wrote.

---

## Orders

### `POST /api/orders`

Place an order. Prices & stock are computed server-side; the client only
provides `listing_id` + `qty`.

- **Body:**
```json
{
  "items": [ { "listing_id": 1, "qty": 5 } ],
  "consumer_phone": "9000000001",
  "consumer_name": "Consumer B",
  "consumer_type": "individual",
  "address": "MG Road, Kochi",
  "payment_method": "UPI",
  "source": "individual"          // or "community" (pool discount applied)
}
```
- **Response (201):** `{ "success": true, "id", "order_code", "subtotal", "delivery_fee", "discount", "total", "eta_minutes", "status", "status_label", "items" }`
- **Errors:** `400`, `404`, `409 INSUFFICIENT_STOCK` (overselling prevented).

### `GET /api/orders?phone=...`

List orders (array). Each order includes `items`, `flow`, `step_index`, `status_label`.

### `GET /api/orders/<id>`

Single order with items.

### `PUT /api/orders/<id>/status`

Advance/change an order status (farmer of the order's listings, the consumer for
cancellation, or admin).

- **Body:** `{ "status": "FARMER_CONFIRMED" }`
- **Statuses:** `ORDER_PLACED → FARMER_CONFIRMED → HARVEST_PACKED → OUT_FOR_DELIVERY → DELIVERED` (plus `CANCELLED`).
- **Errors:** `403 FORBIDDEN`, `409 INVALID_TRANSITION`, `404`.

### `PUT /api/orders/<id>/advance`

Legacy/demo: advance one step in the linear flow (no auth).

---

## Pools

### `GET /api/pools`

Active community pools (array). Includes server-computed `price_now`,
`discount_pct`, `pct`, `current_kg`, `members`, `is_demo`.

### `POST /api/pools/<id>/join`

- **Body:** `{ "qty_kg": 50, "consumer_phone": "...", "consumer_name": "...", "org_name": "..." }`
- **Response:** `{ "success": true, "data": { "pool": { ... } } }`

---

## Subscriptions (HoReCa)

### `POST /api/subscriptions`

Create a recurring subscription. The contract price is computed server-side
(−7% of the listing price).

- **Body:**
```json
{
  "consumer_phone": "9000000001",
  "consumer_name": "Consumer B",
  "org_name": "Cafe Coast",
  "listing_id": 1,
  "qty_kg": 10,
  "frequency": "Weekly",
  "weekdays": ["Mon", "Wed"],
  "time_slot": "6:00 AM - 8:00 AM",
  "start_date": "2026-09-04",
  "end_date": ""
}
```
- **Response (201):** `{ "success": true, "data": { "id", "crop_name", "price_per_kg" } }`

### `GET /api/subscriptions?phone=...`

List subscriptions (array).

### `PUT /api/subscriptions/<id>`

Pause/resume (`active: 0|1` or `status: active|paused|cancelled`) or change `qty_kg`.

### `DELETE /api/subscriptions/<id>`

Cancel. `{ "success": true, "data": { "cancelled": true } }`

### `GET /api/subscriptions/calendar?phone=...&days=30`

Backend-generated delivery calendar:

```json
{
  "schedule": { "2026-09-07": [ { "crop_name", "qty_kg", "price_per_kg", "time_slot", "amount" } ] },
  "days": 30,
  "total_kg": 80,
  "total_amount": 2976.0,
  "delivery_count": 8
}
```

---

## Mandi

### `GET /api/mandi-price?crop=tomato&location=Kochi`

- **Response:**
```json
{
  "crop": "tomato",
  "mandi_price": 22.0,
  "mandi_name": "Azadpur (Delhi) — sample",
  "platform_price": 40.0,
  "uplift_percent": 81.8,
  "extra_earning_per_kg": 18.0,
  "comparison": { "mandi": 22.0, "platform": 40.0 },
  "source": "Demo Market Benchmark",
  "is_live": false,
  "disclaimer": "Demo Market Benchmark — sample data, not live eNAM prices."
}
```

> This is **mock data**, clearly labeled. The provider interface
> (`services/mandi_service.py`) is ready for a real eNAM/Agmarknet source.

---

## AI Grading

### `POST /api/grade`

- **Body:** `{ "crop_name": "Tomato", "harvest_date": "2026-09-03", "photo": "<base64>"? }`
- **Response:** `{ "grade": "A", "grade_desc": "Premium - Export Quality", "freshness_score": 85, "shelf_life": 7, "expiry_date": "2026-09-10", "remaining_days": 6, ... }`

---

## Database & Health

### `GET /api/db-info`

Engine + row counts: `{ "engine": "mysql", "target": "...", "counts": { "listings": 1, ... }, "ok": true, "environment": "development" }`

### `GET /api/health`

`{ "success": true, "data": { "status": "ok", "environment": "development", "engine": "sqlite" } }`

### `GET /api/stats`

Real dashboard numbers: `total_listings`, `grade_a_count`, `total_value`, `farmers`, `consumers`.

---

## Static

| Endpoint | Description |
|---|---|
| `GET /` | Serves the single-page frontend (`index.html`). |
| `GET /uploads/<filename>` | Serves an uploaded crop image. |
