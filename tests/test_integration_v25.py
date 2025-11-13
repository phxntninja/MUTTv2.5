import json
import pytest


pytestmark = pytest.mark.integration


@pytest.fixture
def app(monkeypatch):
    import services.web_ui_service as webui

    # Minimal env to satisfy Config validation
    monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
    monkeypatch.setenv("VAULT_ROLE_ID", "test-role")

    # Avoid real Vault and pools
    def fake_fetch_secrets(app):
        app.config["SECRETS"] = {
            "WEBUI_API_KEY": "it-works",
            # Provide both legacy and dual keys
            "REDIS_PASS": "redis",
            "REDIS_PASS_CURRENT": "redis",
            "DB_USER": "mutt_app",
            "DB_PASS": "db",
            "DB_PASS_CURRENT": "db",
        }
    monkeypatch.setattr(webui, "fetch_secrets", fake_fetch_secrets)

    # Stub pools
    def fake_create_redis_pool(app):
        class DummyPool:
            pass
        app.redis_pool = DummyPool()
    monkeypatch.setattr(webui, "create_redis_pool", fake_create_redis_pool)

    def fake_create_postgres_pool(app):
        class DummyPool:
            def getconn(self):
                return object()
            def putconn(self, _):
                return None
        app.config['DB_POOL'] = DummyPool()
    monkeypatch.setattr(webui, "create_postgres_pool", fake_create_postgres_pool)

    # Use an in-memory DynamicConfig simulation
    class FakeDyn:
        def __init__(self, *_args, **_kwargs):
            self.store = {}
        def start_watcher(self):
            return None
        def get_all(self):
            return dict(self.store)
        def get(self, key, default=None):
            return self.store.get(key, default)
        def set(self, key, value, notify=True):
            self.store[key] = str(value)
    monkeypatch.setattr(webui, "DynamicConfig", FakeDyn)

    # Stub redis.Redis used by DynamicConfig init paths
    monkeypatch.setattr(webui, "redis", type("R", (), {"Redis": staticmethod(lambda **kwargs: object())}))

    app = webui.create_app()
    app.testing = True
    return app

@pytest.mark.usefixtures("app")
class TestV25Integration:
    def test_dynamic_config_end_to_end(self, app):
        client = app.test_client()

        # Update a config key
        resp = client.put(
            "/api/v1/config/cache_reload_interval",
            headers={"X-API-KEY": "it-works", "Content-Type": "application/json"},
            data=json.dumps({"value": "600", "reason": "integration test"}),
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["new_value"] == "600"

        # Now list all config and verify presence
        resp = client.get(
            "/api/v1/config",
            headers={"X-API-KEY": "it-works"},
        )
        assert resp.status_code == 200
        cfg = resp.get_json()["config"]
        assert cfg.get("cache_reload_interval") == "600"

    def test_audit_logger_called_on_update(self, app, monkeypatch):
        import services.web_ui_service as webui
        calls = {}
        def fake_log_config_change(**kwargs):
            calls["last"] = kwargs
            return 1
        monkeypatch.setattr(webui, "log_config_change", fake_log_config_change, raising=False)

        client = app.test_client()
        resp = client.put(
            "/api/v1/config/example_key",
            headers={"X-API-KEY": "it-works", "Content-Type": "application/json"},
            data=json.dumps({"value": "abc"}),
        )
        assert resp.status_code == 200
        assert "last" in calls
        assert calls["last"]["table_name"] == "dynamic_config"


class TestRotationConnectorsIntegration:
    def test_redis_pool_fallback(self, monkeypatch):
        import services.redis_connector as rc
        class FakePool:
            def __init__(self, **kwargs):
                self.password = kwargs.get('password')
        import redis
        monkeypatch.setattr(redis, 'ConnectionPool', lambda **kwargs: FakePool(**kwargs))

        # Fail on CURRENT, succeed on NEXT
        def fake_redis_ctor(connection_pool=None, **kwargs):
            # When initializing with CURRENT, raise
            if getattr(connection_pool, 'password', None) == 'cur':
                raise Exception('auth failed')
            return type("C", (), {"ping": lambda self=None: True})()
        monkeypatch.setattr(redis, 'Redis', fake_redis_ctor)

        pool = rc.get_redis_pool(
            host='h', port=6379, tls_enabled=False,
            password_current='cur', password_next='next'
        )
        assert getattr(pool, 'password') == 'next'

    def test_postgres_pool_fallback(self, monkeypatch):
        import services.postgres_connector as pc
        class FakeConn:
            def cursor(self):
                class Ctx:
                    def __enter__(self):
                        return self
                    def __exit__(self, exc_type, exc, tb):
                        return False
                    def execute(self, _):
                        return None
                return Ctx()
        class FakePool:
            def __init__(self, password):
                if password == 'cur':
                    raise Exception('auth failed')
                self.password = password
            def getconn(self):
                return FakeConn()
            def putconn(self, _):
                return None
        import psycopg2.pool as real_pool
        monkeypatch.setattr(real_pool, "ThreadedConnectionPool", lambda **kwargs: FakePool(kwargs['password']))

        pool = pc.get_postgres_pool(
            host='h', port=5432, dbname='d', user='u',
            password_current='cur', password_next='next',
            minconn=1, maxconn=2
        )
        assert getattr(pool, 'password') == 'next'

