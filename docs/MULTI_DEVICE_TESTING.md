# Farm Bridge — Multi-Device Testing Guide

This is the most important test: a farmer adds a crop from one device and a consumer sees/buys it from another device, and the data persists.

---

## TEST 1 — Farmer creates listing (Device A)

**Device A**: any phone, laptop, or tablet.

1. Open the deployed Farm Bridge URL.
2. Choose **Farmer Portal**.
3. Log in with name + phone (mock OTP in dev).
4. In the crop form:
   - Crop name: **Tomato**
   - Quantity: **100 Kg**
   - Price: **₹40/Kg**
   - Harvest date: **yesterday**
   - Location: **Kochi**
   - Upload an image.
5. Click **List on FARM BRIDGE**.
6. Verify the API response includes `success: true`, a listing `id`, and an AI grade (`A` or `B` depending on freshness).

---

## TEST 2 — Consumer sees listing (Device B)

**Device B**: a different browser (even incognito), different phone, or another laptop.

1. Open the same deployed Farm Bridge URL.
2. Choose **Consumer Portal**.
3. Go to the marketplace.
4. Confirm the **Tomato** listing appears.
5. Verify available quantity is **100 kg** and price is **₹40/kg**.

The listing comes from the central backend database (`GET /api/market`), not browser storage.

---

## TEST 3 — Multi-user order

1. In the Consumer Portal, add **5 Kg** of Tomato to the cart.
2. Checkout and place the order.
3. Verify:
   - Order created successfully (`order_code`, `status: Order Placed`).
   - Database updated.
   - Marketplace available quantity becomes **95 kg**.

---

## TEST 4 — Farmer order view

1. Back on **Device A**, open Farmer Portal.
2. Confirm the incoming order appears.
3. Verify order details:
   - Order ID / order code.
   - Consumer name.
   - Crop: Tomato.
   - Quantity: 5 Kg.
   - Delivery location.
   - Order status: Order Placed.
   - Payment status.

---

## TEST 5 — Persistence

1. **Restart the Render service** (or redeploy).
2. Open the URL on both devices again.
3. Verify:
   - Listings remain.
   - Orders remain.
   - Consumer profiles remain.
   - Subscriptions remain.
   - Stock remains at 95 kg.

> Note: images using `STORAGE_PROVIDER=local` on Render may be lost after redeploy because Render's disk is ephemeral. Use Cloudinary for persistent images.

---

## TEST 6 — Security

From any logged-in user:

- Attempt to **modify another farmer's listing** → expect 403.
- Submit an order with **negative quantity** → expect 400/409.
- Attempt to **buy more stock than available** → expect 409 with a message like `Only 95.0 Kg of Tomato is available`.
- Try to access a protected endpoint without a token → expect 401.
- Inspect any `/api/*` error response → must be structured JSON, no stack traces or SQL.

---

## How to verify the central DB (manual)

```bash
# Health / connection
curl https://your-app.onrender.com/health

# Marketplace (listings from central DB)
curl https://your-app.onrender.com/api/market
```

The same backend + database is used by Farmer and Consumer portals.
