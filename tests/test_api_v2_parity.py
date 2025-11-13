#!/usr/bin/env python3
"""
MUTT v2.5 - v1/v2 API Parity Tests (Web UI)

Verifies that v2 aliases return identical payloads as v1 for key endpoints.
These tests monkeypatch DB/Redis to avoid external dependencies.
"""

import pytest


class FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows if rows is not None else []
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def execute(self, query, params=None):
        pass
    def fetchone(self):
        return (len(self._rows),)
    def fetchall(self):
        return self._rows

class FakeConn:
    def __init__(self, rows=None):
        self._rows = rows
    def cursor(self, *args, **kwargs):
        return FakeCursor(self._rows)
    def commit(self):
        pass
    def rollback(self):
        pass

class FakePool:
    def __init__(self, rows=None):
        self._rows = rows
    def getconn(self):
        return FakeConn(self._rows)
    def putconn(self, _):
        pass

class FakeRedis:
    def __init__(self, *args, **kwargs):
        self.store = {}
    def get(self, key):
        return self.store.get(key)
    def set(self, key, value, *args, **kwargs):
        self.store[key] = value
    def hgetall(self, *args, **kwargs):
        return {}
    def llen(self, *args, **kwargs):
        return 0
    def scan_iter(self, *args, **kwargs):
        yield from []
    def mget(self, keys, *args, **kwargs):
        return [self.store.get(k) for k in keys]

class DummyRedisModule:
    Redis = FakeRedis
    class exceptions:
        class ConnectionError(Exception):
            pass


@pytest.fixture
def app(monkeypatch):
    from services import web_ui_service as w

    # Disable DynamicConfig to avoid Redis requirement
    monkeypatch.setattr(w, 'DynamicConfig', None)

    # Bypass Vault/Redis/Postgres initialization
    def fake_fetch_secrets(app):
        app.config['SECRETS'] = {"WEBUI_API_KEY": "test-api-key-123"}
    monkeypatch.setattr(w, 'fetch_secrets', fake_fetch_secrets)
    monkeypatch.setattr(w, 'create_redis_pool', lambda app: setattr(app, 'redis_pool', object()))
    monkeypatch.setattr(w, 'create_postgres_pool', lambda app: app.config.__setitem__('DB_POOL', None))

    # Build app
    app = w.create_app()
    return app

@pytest.mark.usefixtures("app")
@pytest.mark.unit
class TestV2Parity:
    def test_rules_list_parity(self, app):
        # Inject fake DB pool
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/rules', headers=headers)
        v2 = client.get('/api/v2/rules', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_dev_hosts_parity(self, app):
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/dev-hosts', headers=headers)
        v2 = client.get('/api/v2/dev-hosts', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_teams_parity(self, app):
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/teams', headers=headers)
        v2 = client.get('/api/v2/teams', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_metrics_parity(self, app, monkeypatch):
        # Monkeypatch redis client used by web_ui_service
        class DummyRedisModule:
            Redis = FakeRedis
        monkeypatch.setattr('services.web_ui_service.redis', DummyRedisModule())

        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/metrics', headers=headers)
        v2 = client.get('/api/v2/metrics', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_audit_logs_parity(self, app):
        app.config['DB_POOL'] = FakePool(None)
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/audit-logs?limit=1', headers=headers)
        v2 = client.get('/api/v2/audit-logs?limit=1', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()
