def test_create_listing_requires_auth(client):
    r = client.post('/api/listings', json={
        'crop_name': 'Tomato', 'harvest_date': '2026-09-03',
        'quantity': 100, 'price': 40, 'location': 'Kochi',
    })
    assert r.status_code == 401


def test_create_listing_and_market(client, farmer_headers):
    r = client.post('/api/listings', json={
        'crop_name': 'Tomato', 'harvest_date': '2026-09-03',
        'quantity': 100, 'price': 40, 'location': 'Kochi, Kerala',
    }, headers=farmer_headers)
    assert r.status_code == 201
    assert r.json['data']['grade_info']['grade'] == 'A'

    r = client.get('/api/market')
    assert r.status_code == 200
    assert r.json['data']['count'] == 1
    item = r.json['data']['items'][0]
    assert item['crop_name'] == 'Tomato'
    assert item['available_kg'] == 100
    assert item['price_per_unit'] == 40


def test_get_listing_endpoint(client, farmer_headers):
    data = {
        'crop_name': 'Potato', 'harvest_date': '2026-09-02',
        'quantity': 50, 'price': 30, 'location': 'Palakkad',
    }
    r = client.post('/api/listings', json=data, headers=farmer_headers)
    lid = r.json['data']['id']
    r = client.get('/api/listings/%d' % lid)
    assert r.status_code == 200
    assert r.json['data']['crop_name'] == 'Potato'
