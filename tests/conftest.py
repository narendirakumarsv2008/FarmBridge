import os
import pytest

os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('DB_ENGINE', 'sqlite')


@pytest.fixture()
def app(tmp_path):
    from app import create_app
    db_path = str(tmp_path / 'test_farmbridge.db')
    app = create_app({
        'ENVIRONMENT': 'test',
        'DB_ENGINE': 'sqlite',
        'SQLITE_PATH': db_path,
        'SECRET_KEY': 'test-secret',
    })
    app.config['TESTING'] = True
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, name, phone, role='consumer'):
    r = client.post('/api/auth/request-otp', json={'name': name, 'phone': phone})
    assert r.status_code == 200, r.json
    otp = r.json['data']['demo_otp']
    r = client.post('/api/auth/login', json={'name': name, 'phone': phone, 'otp': otp})
    assert r.status_code == 200, r.json
    return {'Authorization': 'Bearer ' + r.json['data']['token']}


@pytest.fixture()
def farmer_headers(client):
    return _login(client, 'Ramesh Kumar', '9876543210')


@pytest.fixture()
def consumer_headers(client):
    return _login(client, 'Priya Sharma', '9876500001')


def create_listing(client, headers, **overrides):
    payload = {
        'crop_name': 'Tomato',
        'harvest_date': '2026-09-03',
        'quantity': 100,
        'price': 40,
        'location': 'Kochi, Kerala',
        'photo': '',
    }
    payload.update(overrides)
    r = client.post('/api/listings', json=payload, headers=headers)
    assert r.status_code == 201, r.json
    return r.json['data']
