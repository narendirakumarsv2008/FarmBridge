def test_request_otp_and_login(client):
    r = client.post('/api/auth/request-otp', json={'name': 'Ramesh', 'phone': '9876543210'})
    assert r.status_code == 200
    assert r.json['data']['demo_otp']
    otp = r.json['data']['demo_otp']

    r = client.post('/api/auth/login', json={'name': 'Ramesh', 'phone': '9876543210', 'otp': otp})
    assert r.status_code == 200
    assert r.json['data']['token']
    assert r.json['data']['user']['phone'] == '9876543210'


def test_me_requires_token(client):
    r = client.get('/api/auth/me')
    assert r.status_code == 401


def test_me_with_token(client):
    r = client.post('/api/auth/request-otp', json={'name': 'Ramesh', 'phone': '9876543210'})
    otp = r.json['data']['demo_otp']
    r = client.post('/api/auth/login', json={'name': 'Ramesh', 'phone': '9876543210', 'otp': otp})
    token = r.json['data']['token']
    r = client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})
    assert r.status_code == 200
    assert r.json['data']['phone'] == '9876543210'


def test_legacy_login_alias(client):
    r = client.post('/api/login', json={'name': 'Ramesh', 'phone': '9876543210'})
    assert r.status_code == 200
    assert r.json['data']['token']
