from tests.conftest import create_listing


def _buyer_profile(client, headers, phone='9876500001'):
    return client.post('/api/consumer/profile', json={
        'name': 'Priya Sharma', 'phone': phone,
        'email': 'priya@example.com',
        'address': 'Flat 101, MG Road, Kochi',
        'consumer_type': 'Individual',
    }, headers=headers)


def test_order_reduces_stock(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03')
    _buyer_profile(client, consumer_headers)

    r = client.post('/api/orders', json={
        'items': [{'listing_id': listing['id'], 'qty': 5}],
        'payment_method': 'UPI', 'address': 'Kochi',
    }, headers=consumer_headers)
    assert r.status_code == 201, r.json
    assert r.json['data']['subtotal'] == 200

    r = client.get('/api/market')
    item = r.json['data']['items'][0]
    assert item['available_kg'] == 95


def test_overselling_fails(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=10)
    r = client.post('/api/orders', json={
        'items': [{'listing_id': listing['id'], 'qty': 8}],
        'payment_method': 'UPI',
    }, headers=consumer_headers)
    assert r.status_code == 201

    r = client.post('/api/orders', json={
        'items': [{'listing_id': listing['id'], 'qty': 8}],
        'payment_method': 'UPI',
    }, headers=consumer_headers)
    assert r.status_code == 409
    assert 'available' in r.json['error']['message'].lower()


def test_order_items_created(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=20)
    r = client.post('/api/orders', json={
        'items': [{'listing_id': listing['id'], 'qty': 3, 'price': 999}],
        'payment_method': 'UPI',
    }, headers=consumer_headers)
    oid = r.json['data']['id']
    r = client.get('/api/orders/%d' % oid, headers=consumer_headers)
    assert r.status_code == 200
    # Backend uses authoritative price 40, not the client-sent 999.
    assert r.json['data']['order_items'][0]['price_per_unit'] == 40
    assert r.json['data']['order_items'][0]['quantity'] == 3


def test_status_transitions(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=20)
    r = client.post('/api/orders', json={
        'items': [{'listing_id': listing['id'], 'qty': 2}],
        'payment_method': 'UPI',
    }, headers=consumer_headers)
    oid = r.json['data']['id']

    r = client.put('/api/orders/%d/status' % oid, json={'status': 'FARMER_CONFIRMED'},
                   headers=farmer_headers)
    assert r.status_code == 200
    assert r.json['data']['status_code'] == 'FARMER_CONFIRMED'

    r = client.put('/api/orders/%d/status' % oid, json={'status': 'DELIVERED'},
                   headers=farmer_headers)
    assert r.status_code == 409


def test_farmer_orders(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=20)
    client.post('/api/orders', json={
        'items': [{'listing_id': listing['id'], 'qty': 2}],
        'payment_method': 'UPI',
    }, headers=consumer_headers)
    r = client.get('/api/farmer/orders', headers=farmer_headers)
    assert r.status_code == 200
    assert r.json['data']['count'] == 1
