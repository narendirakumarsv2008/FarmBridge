# Farm Bridge API Documentation

All API responses use a consistent envelope.

**Success**

```json
{
  "success": true,
  "data": {}
}
```

**Error**

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Quantity must be greater than zero"
  }
}
```

Common HTTP statuses: `200`, `201`, `400`, `401`, `403`, `404`, `409`, `500`.

---

## Authentication

### POST `/api/auth/request-otp`

Request an OTP for a phone number. In development (mock SMS provider) the response includes `demo_otp`.

**Body**

```json
{
  "name": "Ramesh Kumar",
  "phone": "9876543210"
}
```

**Response 200**

```json
{
  "success": true,
  "data": {
    "otp_sent": true,
    "phone": "9876543210",
    "demo_otp": "123456",
    "dev": true,
    "provider": "mock"
  }
}
```

**curl**

```bash
curl -X POST http://localhost:5000/api/auth/request-otp \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ramesh Kumar","phone":"9876543210"}'
```

### POST `/api/auth/login`

Verify the OTP and receive a JWT.

**Body**

```json
{
  "name": "Ramesh Kumar",
  "phone": "9876543210",
  "otp": "123456"
}
```

**Response 200**

```json
{
  "success": true,
  "data": {
    "token": "<jwt>",
    "user": {
      "id": 1,
      "name": "Ramesh Kumar",
      "phone": "9876543210",
      "email": "",
      "role": "consumer"
    }
  }
}
```

Use the token on protected endpoints:

```bash
Authorization: Bearer <jwt>
```

### GET `/api/auth/me`

Returns the logged-in user.

**Auth:** yes

### POST `/api/auth/logout`

Client-side logout endpoint. JWT is stateless; the client discards its token.

**Auth:** yes

### POST `/api/login` (deprecated alias)

Legacy name+phone login. Returns the same token/user shape for backward compatibility.

---

## Farmer

### GET `/api/farmer/profile`

Returns the current user's farmer profile.

**Auth:** yes

### PUT `/api/farmer/profile`

Create/update farmer profile.

**Body**

```json
{
  "farm_name": "Green Valley Farm",
  "location": "Kochi",
  "city": "Ernakulam",
  "state": "Kerala",
  "pincode": "682001",
  "latitude": 9.93,
  "longitude": 76.26
}
```

### GET `/api/farmer/listings`

Returns listings owned by the current user.

**Auth:** yes

### GET `/api/farmer/orders`

Returns orders that contain at least one listing owned by the current farmer.

**Auth:** yes

---

## Listings

### POST `/api/listings`

Create a crop listing.

**Auth:** yes

**Body**

```json
{
  "crop_name": "Tomato",
  "harvest_date": "2026-09-03",
  "quantity": 100,
  "price": 40,
  "location": "Kochi, Kerala",
  "photo": "<optional data:image/jpeg;base64,...>",
  "voice_transcript": "I am growing tomato..."
}
```

**Response 201**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "grade_info": {
      "grade": "A",
      "freshness_score": 85,
      "expiry_date": "2026-09-10",
      "shelf_life": 7
    },
    "mandi_name": "Azadpur Mandi, Delhi",
    "platform_price": 40,
    "image_url": "/uploads/abc.jpg"
  }
}
```

### GET `/api/listings`

Returns marketplace listings.

**Auth:** no

**Response**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1,
        "crop_name": "Tomato",
        "available_kg": 95,
        "price_per_unit": 40,
        "grade": "A",
        "photo": "/uploads/abc.jpg"
      }
    ],
    "count": 1
  }
}
```

### GET `/api/listings/<id>`

Returns a single listing.

### PUT `/api/listings/<id>`

Update a listing. The user must own the listing.

**Body**

```json
{
  "crop_name": "Tomato",
  "quantity": 120,
  "price": 42,
  "location": "Kochi",
  "status": "active"
}
```

### DELETE `/api/listings/<id>`

Marks a listing as inactive (soft delete).

**Auth:** yes, owner only.

### PUT `/api/listings/<id>/status`

Set listing status: `active`, `low_stock`, `sold_out`, `expired`, `inactive`.

---

## Marketplace

### GET `/api/market`

The shared consumer marketplace. Reads real listings from the central database.

**Auth:** no

**Query**

- None required.

**Response**

```json
{
  "success": true,
  "data": {
    "items": [],
    "count": 0,
    "updated_at": "2026-09-04T12:00:00"
  }
}
```

---

## Consumer

### GET `/api/consumer/profile`

Fetch the consumer profile for the logged-in user.

**Auth:** yes

**Query**

```text
phone=9876500001
```

### POST `/api/consumer/profile`

Create/update consumer profile.

**Auth:** yes

**Body**

```json
{
  "name": "Priya Sharma",
  "phone": "9876500001",
  "email": "priya@example.com",
  "address": "Flat 101, MG Road, Kochi",
  "consumer_type": "Individual",
  "city": "Kochi",
  "pincode": "682001",
  "org_name": "Green Meadows"
}
```

`consumer_type` accepts `Individual`, `Community`, `HoReCa`.

### PUT `/api/consumer/profile`

Same as POST.

### GET/POST `/api/buyer/profile` (deprecated alias)

Temporarily retained so old frontends continue to work. Returns `buyer_type` in the legacy shape.

---

## Orders

### POST `/api/orders`

Place an order. The backend recalculates every price from the listing (or the pool price) and protects stock with a transaction.

**Auth:** yes

**Body**

```json
{
  "items": [
    {
      "listing_id": 1,
      "qty": 5,
      "pool_id": null
    }
  ],
  "buyer_phone": "9876500001",
  "buyer_name": "Priya Sharma",
  "address": "Flat 101, MG Road, Kochi",
  "payment_method": "UPI",
  "source": "individual"
}
```

**Response 201**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "order_code": "FB2609041234",
    "status_code": "ORDER_PLACED",
    "status": "Order Placed",
    "subtotal": 200,
    "delivery_fee": 25,
    "discount": 0,
    "total": 225,
    "eta_minutes": 14,
    "items": []
  }
}
```

### GET `/api/orders`

List orders for the logged-in consumer.

**Auth:** yes

**Query**

```text
phone=9876500001
```

### GET `/api/orders/<id>`

Return one order with `order_items`.

**Auth:** yes

### PUT `/api/orders/<id>/status`

Set an order status (controlled transitions).

**Auth:** yes

**Body**

```json
{
  "status": "FARMER_CONFIRMED"
}
```

Allowed statuses: `ORDER_PLACED`, `FARMER_CONFIRMED`, `HARVEST_PACKED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED`.

Valid transitions:

```
ORDER_PLACED -> FARMER_CONFIRMED / CANCELLED
FARMER_CONFIRMED -> HARVEST_PACKED / CANCELLED
HARVEST_PACKED -> OUT_FOR_DELIVERY / CANCELLED
OUT_FOR_DELIVERY -> DELIVERED
```

### PUT `/api/orders/<id>/advance` (demo alias)

Auto-advances to the next status.

**Auth:** yes

---

## Pools

### GET `/api/pools`

List open community pools. Pools are generated from real listings and are labelled as demo community data.

**Auth:** no

### POST `/api/pools/<id>/join`

Join a pool.

**Auth:** yes

**Body**

```json
{
  "qty_kg": 25,
  "buyer_phone": "9876500001",
  "buyer_name": "Priya Sharma",
  "org_name": "Green Meadows"
}
```

---

## Subscriptions

### GET `/api/subscriptions`

List subscriptions.

**Auth:** yes

**Query**

```text
phone=9876500001
```

### POST `/api/subscriptions`

Create a subscription.

**Auth:** yes

**Body**

```json
{
  "buyer_phone": "9876500001",
  "buyer_name": "Priya Sharma",
  "org_name": "Cafe Coast",
  "crop_name": "Tomato",
  "listing_id": 1,
  "qty_kg": 25,
  "price_per_kg": 37.2,
  "frequency": "Weekly",
  "weekdays": ["Mon", "Thu"],
  "time_slot": "6:00 AM - 8:00 AM",
  "start_date": "2026-09-01",
  "end_date": "2026-12-31"
}
```

### PUT `/api/subscriptions/<id>`

Pause/resume or update quantity.

**Body**

```json
{
  "active": 0,
  "qty_kg": 30
}
```

### DELETE `/api/subscriptions/<id>`

Cancel a subscription.

**Auth:** yes

### GET `/api/subscriptions/calendar`

Backend-generated delivery calendar.

**Auth:** yes

**Query**

```text
phone=9876500001&days=30
```

---

## Mandi & Grading

### GET `/api/mandi-price`

Demo/estimated Mandi market benchmark. Explicitly labelled as demo data.

**Query**

```text
crop=Tomato&location=Kochi
```

**Response**

```json
{
  "success": true,
  "data": {
    "crop": "tomato",
    "mandi_price": 22,
    "platform_price": 26.4,
    "data_source": "Demo Market Benchmark",
    "source_label": "Mock Mandi Data",
    "is_demo": true
  }
}
```

### POST `/api/grade`

AI freshness grading.

**Body**

```json
{
  "crop_name": "Tomato",
  "harvest_date": "2026-09-03",
  "photo": "<optional data URL>"
}
```

---

## System

### GET `/health`

Liveness/health check. Returns `200` when the DB is connected, `503` when degraded.

```json
{
  "status": "ok",
  "app": "FarmBridge",
  "database": {"engine": "mysql", "connected": true}
}
```

### GET `/api/health`

Machine-friendly health endpoint designed for Render health checks.

**Response 200**

```json
{
  "status": "healthy",
  "service": "farmbridge",
  "database": "connected"
}
```

Returns `503` with `database: disconnected` if the DB is unreachable.

### GET `/api/db-info`

Safe diagnostic endpoint. Never exposes passwords, connection strings, or internal SQL.

```json
{
  "engine": "mysql",
  "connected": true,
  "environment": "production"
}
```

In non-production environments it also returns table `counts`.

---

## Error handling

| HTTP | Code | Example |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Quantity must be greater than zero |
| 401 | `UNAUTHORIZED` | Authentication required |
| 403 | `FORBIDDEN` | You cannot modify another farmer's listing |
| 404 | `NOT_FOUND` | Listing not found |
| 409 | `CONFLICT` | Only 95.0 Kg of Tomato is available |
| 500 | `INTERNAL_ERROR` | Internal server error |
