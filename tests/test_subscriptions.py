from tests.conftest import create_listing


def _sub_payload(listing):
    return {
        'buyer_phone': '9876500001',
        'buyer_name': 'Priya Sharma',
        'org_name': 'Cafe Coast',
        'crop_name': 'Tomato',
        'listing_id': listing['id'],
        'qty_kg': 25,
        'price_per_kg': 37.2,
        'frequency': 'Weekly',
        'weekdays': ['Mon', 'Thu'],
        'time_slot': '6:00 AM - 8:00 AM',
        'start_date': '2026-09-01',
        'end_date': '2026-12-31',
    }


def test_create_and_list_subscriptions(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=100)
    r = client.post('/api/subscriptions', json=_sub_payload(listing), headers=consumer_headers)
    assert r.status_code == 201, r.json
    sid = r.json['data']['id']

    r = client.get('/api/subscriptions?phone=9876500001', headers=consumer_headers)
    assert r.status_code == 200
    assert r.json['data']['count'] == 1


def test_calendar_has_deliveries(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=100)
    client.post('/api/subscriptions', json=_sub_payload(listing), headers=consumer_headers)
    r = client.get('/api/subscriptions/calendar?days=30&phone=9876500001',
                   headers=consumer_headers)
    assert r.status_code == 200
    schedule = r.json['data']['schedule']
    assert schedule, r.json


def test_pause_resume_cancel(client, farmer_headers, consumer_headers):
    listing = create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=100)
    r = client.post('/api/subscriptions', json=_sub_payload(listing), headers=consumer_headers)
    sid = r.json['data']['id']

    r = client.put('/api/subscriptions/%d' % sid, json={'active': 0}, headers=consumer_headers)
    assert r.status_code == 200

    r = client.delete('/api/subscriptions/%d' % sid, headers=consumer_headers)
    assert r.status_code == 200
