def test_save_and_get_consumer_profile(client, consumer_headers):
    r = client.post('/api/consumer/profile', json={
        'name': 'Priya Sharma', 'phone': '9876500001',
        'email': 'priya@example.com', 'address': 'Flat 101 MG Road Kochi',
        'consumer_type': 'Community', 'org_name': 'Green Meadows',
    }, headers=consumer_headers)
    assert r.status_code == 201, r.json
    assert r.json['data']['profile']['consumer_type'] == 'community'

    r = client.get('/api/consumer/profile?phone=9876500001', headers=consumer_headers)
    assert r.status_code == 200
    assert r.json['data']['found'] is True
    assert r.json['data']['profile']['organization_name'] == 'Green Meadows'


def test_buyer_profile_alias(client, consumer_headers):
    r = client.post('/api/buyer/profile', json={
        'name': 'Priya Sharma', 'phone': '9876500001',
        'email': 'priya@example.com', 'address': 'Flat 101 MG Road Kochi',
        'buyer_type': 'Individual',
    }, headers=consumer_headers)
    assert r.status_code == 201, r.json
    assert r.json['data']['profile']['buyer_type'] == 'Individual'
