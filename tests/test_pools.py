from tests.conftest import create_listing


def test_list_pools(client, farmer_headers):
    create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=100)
    r = client.get('/api/pools')
    assert r.status_code == 200
    assert r.json['data']['items']
    assert r.json['data']['items'][0]['is_demo'] is True


def test_join_pool(client, farmer_headers, consumer_headers):
    create_listing(client, farmer_headers, harvest_date='2026-09-03', quantity=100)
    pools = client.get('/api/pools').json['data']['items']
    pool_id = pools[0]['id']
    r = client.post('/api/pools/%d/join' % pool_id, json={
        'qty_kg': 25,
        'buyer_phone': '9876500001',
        'buyer_name': 'Priya Sharma',
    }, headers=consumer_headers)
    assert r.status_code == 201, r.json
