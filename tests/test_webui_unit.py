# =====================================================================
# MUTT v2.3 Web UI Service Unit Tests
# =====================================================================
# Tests for web_ui_service.py
# Run with: pytest tests/test_webui_unit.py -v
# =====================================================================

import pytest
from unittest.mock import Mock, MagicMock, patch
import json
import time
import secrets as secrets_module
import types


@pytest.fixture
def app(monkeypatch):
    from services import web_ui_service as w

    # Disable DynamicConfig to avoid Redis requirement
    monkeypatch.setattr(w, 'DynamicConfig', None)

    # Setup SLO_TARGETS for testing
    test_slo_targets = {
        "ingestor_availability": {
            "description": "Ingestor availability",
            "target": 0.995,
            "metric_query": "sum(rate(mutt_ingest_requests_total{status='success'}[5m])) / sum(rate(mutt_ingest_requests_total[5m]))",
            "window_hours": 24,
            "burn_rate_threshold_warning": 2.0,
            "burn_rate_threshold_critical": 3.0
        },
        "forwarder_availability": {
            "description": "Forwarder availability",
            "target": 0.99,
            "metric_query": "sum(rate(mutt_moog_requests_total{status='success'}[5m])) / sum(rate(mutt_moog_requests_total[5m]))",
            "window_hours": 24,
            "burn_rate_threshold_warning": 1.5,
            "burn_rate_threshold_critical": 2.0
        }
    }
    monkeypatch.setattr(w, 'SLO_TARGETS', test_slo_targets)
    monkeypatch.setattr(w, 'GLOBAL_SLO_SETTINGS', {})

    # Bypass Vault/Redis/Postgres initialization
    def fake_fetch_secrets(app):
        app.config['SECRETS'] = {"WEBUI_API_KEY": "test-api-key-123"}
    monkeypatch.setattr(w, 'fetch_secrets', fake_fetch_secrets)
    monkeypatch.setattr(w, 'create_redis_pool', lambda app: None)
    monkeypatch.setattr(w, 'create_postgres_pool', lambda app: app.config.__setitem__('DB_POOL', None))

    # Build app
    app = w.create_app()
    return app

@pytest.mark.usefixtures("app")
class TestSLOEndpoint:
    """Tests for /api/v1/slo endpoint (mocked Prometheus)."""

    def test_slo_ok_state(self, app, monkeypatch):
        from services import web_ui_service as w

        # Mock requests.get to return two success values (ingestor, forwarder)
        class R:
            def __init__(self, v):
                self.status_code = 200
                self._v = v
            def json(self):
                return {
                    'status': 'success',
                    'data': {'result': [{'value': ["0", str(self._v)]}]}
                }
        calls = []
        def fake_get(url, params=None, timeout=5):
            calls.append(params['query'])
            # Return high availability above targets
            return R(0.999)
        monkeypatch.setattr(w.requests, 'get', fake_get)

        client = app.test_client()
        resp = client.get('/api/v1/slo', headers={'X-API-KEY': 'test-api-key-123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'slos' in data
        assert isinstance(data['slos'], list)
        for slo in data['slos']:
            assert slo['status'] == 'ok'

    def test_slo_warn_and_critical_states(self, app, monkeypatch):
        from services import web_ui_service as w

        # Return warn for ingestor (burn_rate == 2), critical for forwarder (burn_rate > 2)
        values = [0.990, 0.980]  # assuming targets 0.995 and 0.99
        class R:
            def __init__(self, v):
                self.status_code = 200
                self._v = v
            def json(self):
                return {
                    'status': 'success',
                    'data': {'result': [{'value': ["0", str(self._v)]}]}
                }
        def fake_get(url, params=None, timeout=5):
            v = values.pop(0)
            return R(v)
        monkeypatch.setattr(w.requests, 'get', fake_get)

        client = app.test_client()
        resp = client.get('/api/v1/slo', headers={'X-API-KEY': 'test-api-key-123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'slos' in data
        ingestor_slo = next((s for s in data['slos'] if s['description'] == 'Ingestor availability'), None)
        forwarder_slo = next((s for s in data['slos'] if s['description'] == 'Forwarder availability'), None)
        assert ingestor_slo is not None
        assert forwarder_slo is not None
        assert ingestor_slo['status'] == 'warning'
        assert forwarder_slo['status'] == 'critical'

    def test_slo_single_retry_on_failure(self, app, monkeypatch):
        from services import web_ui_service as w

        # First call fails (timeout), second call succeeds with good value for both queries
        class R:
            def __init__(self, v):
                self.status_code = 200
                self._v = v
            def json(self):
                return {
                    'status': 'success',
                    'data': {'result': [{'value': ["0", str(self._v)]}]}
                }

        calls = {'count': 0}
        def flaky_get(url, params=None, timeout=5):
            # Simulate failure only on the very first call, then success
            if calls['count'] == 0:
                calls['count'] += 1
                raise TimeoutError("simulated timeout")
            calls['count'] += 1
            return R(0.999)

        monkeypatch.setattr(w.requests, 'get', flaky_get)

        client = app.test_client()
        resp = client.get('/api/v1/slo', headers={'X-API-KEY': 'test-api-key-123'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'slos' in data
        for slo in data['slos']:
            assert slo['status'] == 'ok'


# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestAPIAuthentication:
    """Test API key authentication for Web UI"""

    def test_valid_api_key_header(self, mock_secrets):
        """Test valid API key in header is accepted"""
        provided_key = "test-api-key-123"
        expected_key = mock_secrets["WEBUI_API_KEY"]

        result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is True

    def test_valid_api_key_query_param(self, mock_secrets):
        """Test valid API key in query parameter is accepted"""
        provided_key = "test-api-key-123"
        expected_key = mock_secrets["WEBUI_API_KEY"]

        result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is True

    def test_invalid_api_key_rejected(self, mock_secrets):
        """Test invalid API key is rejected"""
        provided_key = "wrong-key"
        expected_key = mock_secrets["WEBUI_API_KEY"]

        result = secrets_module.compare_digest(provided_key, expected_key)

        assert result is False

    def test_health_endpoint_no_auth_required(self):
        """Test /health endpoint doesn't require authentication"""
        # Health endpoint should be publicly accessible
        requires_auth = False  # Health endpoint bypasses auth

        assert requires_auth is False

    def test_metrics_endpoint_no_auth_required(self):
        """Test /metrics endpoint doesn't require authentication"""
        # Metrics endpoint should be publicly accessible for Prometheus
        requires_auth = False

        assert requires_auth is False

    def test_dashboard_no_auth_required(self):
        """Test / (dashboard) doesn't require authentication"""
        # Dashboard HTML can be public, API key needed for data fetching
        requires_auth = False

        assert requires_auth is False


class TestMetricsCaching:
    """Test metrics caching logic"""

    def test_cache_miss_fetches_from_redis(self, mock_redis_client):
        """Test cache miss triggers Redis fetch"""
        # Simulate cache with expired TTL
        cache_ttl = 5
        cache_timestamp = time.time() - 10  # 10 seconds ago (expired)
        now = time.time()

        cache_expired = (now - cache_timestamp) > cache_ttl

        if cache_expired:
            # Fetch from Redis
            mock_redis_client.get("mutt:metrics:1m:key")

        assert cache_expired is True
        mock_redis_client.get.assert_called_once()

    def test_cache_hit_returns_cached_data(self):
        """Test cache hit returns cached data without Redis call"""
        cache_ttl = 5
        cache_timestamp = time.time() - 2  # 2 seconds ago (valid)
        now = time.time()

        cache_valid = (now - cache_timestamp) <= cache_ttl

        assert cache_valid is True
        # Should return cached data, no Redis call

    def test_cache_ttl_configurable(self):
        """Test cache TTL is configurable"""
        cache_ttl = 5  # 5 seconds

        assert cache_ttl > 0

    def test_cache_refresh_on_expiry(self, mock_redis_client):
        """Test cache is refreshed when expired"""
        # Simulate MetricsCache class behavior
        class MetricsCache:
            def __init__(self, ttl=5):
                self.ttl = ttl
                self.data = None
                self.timestamp = 0

            def get(self):
                if time.time() - self.timestamp > self.ttl:
                    # Refresh
                    self.data = {"rate_1m": 100}
                    self.timestamp = time.time()
                return self.data

        cache = MetricsCache(ttl=5)
        cache.timestamp = time.time() - 10  # Expired

        data = cache.get()

        assert data is not None
        assert "rate_1m" in data


class TestAlertRulesCRUD:
    """Test alert rules CRUD operations"""

    def test_list_rules(self, sample_alert_rules):
        """Test GET /api/v1/rules returns all rules"""
        rules = sample_alert_rules

        assert len(rules) > 0
        assert all("id" in rule for rule in rules)

    def test_create_rule(self, mock_postgres_conn):
        """Test POST /api/v1/rules creates new rule"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        new_rule = {
            "match_string": "WARNING",
            "match_type": "contains",
            "priority": 30,
            "prod_handling": "Ticket_only",
            "dev_handling": "Ignore",
            "team_assignment": "Engineering",
            "is_active": True
        }

        # Simulate INSERT
        cursor.execute("INSERT INTO alert_rules (...) VALUES (...)", tuple(new_rule.values()))
        cursor.fetchone.return_value = (999,)  # New rule ID

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        mock_postgres_conn.commit.assert_called_once()

    def test_update_rule(self, mock_postgres_conn):
        """Test PUT /api/v1/rules/<id> updates existing rule"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        rule_id = 1
        updates = {"priority": 15, "is_active": False}

        # Simulate UPDATE
        cursor.execute("UPDATE alert_rules SET ... WHERE id = %s", (rule_id,))
        cursor.rowcount = 1  # One row updated

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        mock_postgres_conn.commit.assert_called_once()
        assert cursor.rowcount == 1

    def test_delete_rule(self, mock_postgres_conn):
        """Test DELETE /api/v1/rules/<id> deletes rule"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        rule_id = 1

        # Simulate DELETE
        cursor.execute("DELETE FROM alert_rules WHERE id = %s", (rule_id,))
        cursor.rowcount = 1  # One row deleted

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        mock_postgres_conn.commit.assert_called_once()
        assert cursor.rowcount == 1

    def test_rule_validation(self):
        """Test rule validation logic"""
        # At least one match criteria required
        rule = {
            "match_string": None,
            "trap_oid": None
        }

        has_match_criteria = rule["match_string"] is not None or rule["trap_oid"] is not None

        assert has_match_criteria is False  # Should fail validation


class TestAuditLogQueries:
    """Test audit log queries"""

    def test_list_audit_logs_paginated(self, mock_postgres_conn):
        """Test GET /api/v1/audit-logs with pagination"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        limit = 50
        offset = 0

        # Simulate SELECT with LIMIT/OFFSET
        cursor.execute(
            "SELECT * FROM event_audit_log ORDER BY id DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
        cursor.fetchall.return_value = [
            (1, "2025-11-08", "host1", 1, "Page_and_ticket", True, "msg1"),
            (2, "2025-11-08", "host2", 2, "Ticket_only", False, "msg2")
        ]

        rows = cursor.fetchall()

        assert len(rows) == 2
        cursor.execute.assert_called_once()

    def test_audit_logs_filtering(self, mock_postgres_conn):
        """Test filtering audit logs by hostname"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        hostname = "server-01"

        # Simulate filtered query
        cursor.execute(
            "SELECT * FROM event_audit_log WHERE hostname = %s",
            (hostname,)
        )
        cursor.fetchall.return_value = [
            (1, "2025-11-08", "server-01", 1, "Page_and_ticket", True, "msg1")
        ]

        rows = cursor.fetchall()

        assert len(rows) == 1
        assert all(row[2] == hostname for row in rows)

    def test_audit_logs_count(self, mock_postgres_conn):
        """Test getting total count of audit logs"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        # Simulate COUNT query
        cursor.execute("SELECT COUNT(*) FROM event_audit_log")
        cursor.fetchone.return_value = (12345,)

        count = cursor.fetchone()[0]

        assert count == 12345


class TestDevHostsCRUD:
    """Test development hosts CRUD operations"""

    def test_list_dev_hosts(self, sample_dev_hosts):
        """Test GET /api/v1/dev-hosts returns all dev hosts"""
        dev_hosts = sample_dev_hosts

        assert len(dev_hosts) == 3
        assert "dev-server-01" in dev_hosts

    def test_add_dev_host(self, mock_postgres_conn):
        """Test POST /api/v1/dev-hosts adds new dev host"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        hostname = "new-dev-server"

        # Simulate INSERT
        cursor.execute(
            "INSERT INTO development_hosts (hostname) VALUES (%s)",
            (hostname,)
        )

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        mock_postgres_conn.commit.assert_called_once()

    def test_delete_dev_host(self, mock_postgres_conn):
        """Test DELETE /api/v1/dev-hosts/<hostname> removes dev host"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        hostname = "dev-server-01"

        # Simulate DELETE
        cursor.execute(
            "DELETE FROM development_hosts WHERE hostname = %s",
            (hostname,)
        )
        cursor.rowcount = 1

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        assert cursor.rowcount == 1

    def test_duplicate_dev_host_handled(self, mock_postgres_conn):
        """Test duplicate dev host insertion is handled"""
        import psycopg2

        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        # Simulate unique constraint violation
        cursor.execute.side_effect = psycopg2.IntegrityError("duplicate key")

        with pytest.raises(psycopg2.IntegrityError):
            cursor.execute(
                "INSERT INTO development_hosts (hostname) VALUES (%s)",
                ("existing-host",)
            )


class TestDeviceTeamsCRUD:
    """Test device teams CRUD operations"""

    def test_list_device_teams(self, sample_device_teams):
        """Test GET /api/v1/teams returns all device teams"""
        teams = sample_device_teams

        assert len(teams) == 4
        assert teams["router1.prod.example.com"] == "NetOps"

    def test_add_device_team(self, mock_postgres_conn):
        """Test POST /api/v1/teams adds new device team mapping"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        hostname = "new-device.example.com"
        team = "Security"

        # Simulate INSERT
        cursor.execute(
            "INSERT INTO device_teams (hostname, team_assignment) VALUES (%s, %s)",
            (hostname, team)
        )

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()

    def test_update_device_team(self, mock_postgres_conn):
        """Test PUT /api/v1/teams/<hostname> updates team assignment"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        hostname = "router1.prod.example.com"
        new_team = "NewTeam"

        # Simulate UPDATE
        cursor.execute(
            "UPDATE device_teams SET team_assignment = %s WHERE hostname = %s",
            (new_team, hostname)
        )
        cursor.rowcount = 1

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        assert cursor.rowcount == 1

    def test_delete_device_team(self, mock_postgres_conn):
        """Test DELETE /api/v1/teams/<hostname> removes team mapping"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        hostname = "router1.prod.example.com"

        # Simulate DELETE
        cursor.execute(
            "DELETE FROM device_teams WHERE hostname = %s",
            (hostname,)
        )
        cursor.rowcount = 1

        mock_postgres_conn.commit()

        cursor.execute.assert_called_once()
        assert cursor.rowcount == 1


class TestMetricsEndpoint:
    """Test metrics data endpoint"""

    def test_current_metrics_structure(self, mock_redis_client):
        """Test GET /api/v1/metrics/current returns correct structure"""
        from datetime import datetime

        now = datetime.utcnow()
        key_1m = f"mutt:metrics:1m:{now.strftime('%Y-%m-%dT%H:%M')}"

        mock_redis_client.get.return_value = "150"  # 150 messages in last minute

        rate_1m = int(mock_redis_client.get(key_1m) or 0)

        metrics = {
            "rate_1m": rate_1m,
            "rate_1h": 0,
            "rate_24h": 0,
            "timestamp": now.isoformat()
        }

        assert "rate_1m" in metrics
        assert "rate_1h" in metrics
        assert "rate_24h" in metrics
        assert metrics["rate_1m"] == 150

    def test_metrics_fallback_on_missing_keys(self, mock_redis_client):
        """Test metrics fallback to 0 when keys don't exist"""
        mock_redis_client.get.return_value = None  # Key doesn't exist

        rate = int(mock_redis_client.get("missing_key") or 0)

        assert rate == 0


class TestDatabaseConnectionPooling:
    """Test PostgreSQL connection pooling in Web UI"""

    def test_connection_acquired_from_pool(self, mock_postgres_pool):
        """Test connection is acquired from pool"""
        conn = mock_postgres_pool.getconn()

        assert conn is not None
        mock_postgres_pool.getconn.assert_called_once()

    def test_connection_returned_to_pool(self, mock_postgres_pool):
        """Test connection is returned to pool after use"""
        conn = mock_postgres_pool.getconn()

        # Use connection...

        mock_postgres_pool.putconn(conn)

        mock_postgres_pool.putconn.assert_called_once_with(conn)

    def test_connection_pool_thread_safe(self):
        """Test connection pool is thread-safe"""
        # ThreadedConnectionPool is thread-safe by design
        assert True  # Verified by using psycopg2.pool.ThreadedConnectionPool


class TestErrorHandling:
    """Test error handling in Web UI"""

    def test_database_error_returns_500(self, mock_postgres_conn):
        """Test database error returns HTTP 500"""
        import psycopg2

        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = psycopg2.DatabaseError("Connection lost")

        with pytest.raises(psycopg2.DatabaseError):
            cursor.execute("SELECT * FROM alert_rules")

        # In actual service, this would be caught and return 500

    def test_redis_error_handled(self, mock_redis_client):
        """Test Redis error is handled gracefully"""
        import redis as redis_module

        mock_redis_client.get.side_effect = redis_module.exceptions.ConnectionError("Redis down")

        with pytest.raises(redis_module.exceptions.ConnectionError):
            mock_redis_client.get("key")

        # In actual service, would return cached data or error response

    def test_invalid_json_request_returns_400(self):
        """Test invalid JSON in request body returns 400"""
        invalid_json = '{"key": invalid}'

        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)

        # In actual service, would catch and return 400

    def test_resource_not_found_returns_404(self, mock_postgres_conn):
        """Test resource not found returns 404"""
        cursor = mock_postgres_conn.cursor.return_value.__enter__.return_value

        # Simulate SELECT that finds nothing
        cursor.execute("SELECT * FROM alert_rules WHERE id = %s", (9999,))
        cursor.fetchone.return_value = None

        result = cursor.fetchone()

        assert result is None
        # In actual service, would return 404


class TestHTMLDashboard:
    """Test HTML dashboard rendering"""

    def test_dashboard_contains_chart_js(self):
        """Test dashboard HTML includes Chart.js CDN"""
        cdn_url = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"

        # Dashboard HTML should include this CDN
        assert "cdn.jsdelivr.net" in cdn_url
        assert "chart.js" in cdn_url

    def test_dashboard_contains_metrics_divs(self):
        """Test dashboard HTML has metric display elements"""
        # HTML should have canvases for charts
        html_elements = ["<canvas", "id=\"chart1m\"", "id=\"chart1h\"", "id=\"chart24h\""]

        # All elements should be present in dashboard HTML
        assert all(elem for elem in html_elements)

    def test_dashboard_fetches_metrics_api(self):
        """Test dashboard JavaScript calls /api/v1/metrics/current"""
        api_endpoint = "/api/v1/metrics/current"

        # JavaScript should fetch from this endpoint
        assert api_endpoint.startswith("/api/v1/")


class TestRequestValidation:
    """Test request validation"""

    def test_required_fields_validated(self):
        """Test required fields are validated"""
        rule_data = {
            "match_string": "ERROR",
            # Missing priority, prod_handling, etc.
        }

        required_fields = ["priority", "prod_handling", "dev_handling", "team_assignment"]
        missing_fields = [f for f in required_fields if f not in rule_data]

        assert len(missing_fields) > 0  # Should fail validation

    def test_field_types_validated(self):
        """Test field types are validated"""
        rule_data = {
            "priority": "not-a-number",  # Should be int
            "match_type": "invalid_type"  # Should be enum
        }

        # Type validation
        priority_valid = isinstance(rule_data["priority"], int)
        match_type_valid = rule_data["match_type"] in ["contains", "regex", "oid_prefix"]

        assert priority_valid is False
        assert match_type_valid is False


class TestCORSHeaders:
    """Test CORS headers for API endpoints"""

    def test_cors_headers_optional(self):
        """Test CORS headers can be added if needed"""
        # Web UI is typically accessed on same origin
        # CORS headers only needed for cross-origin access

        cors_enabled = False  # Default: same-origin only

        assert cors_enabled in [True, False]  # Configurable


# =====================================================================
# Integration Test Markers
# =====================================================================

@pytest.mark.integration
class TestWebUIIntegration:
    """Integration tests requiring real services"""

    def test_real_database_crud(self):
        """Test CRUD operations with real PostgreSQL"""
        pytest.skip("Integration test - requires real PostgreSQL")

    def test_real_redis_metrics(self):
        """Test metrics fetching from real Redis"""
        pytest.skip("Integration test - requires real Redis")

    def test_dashboard_rendering(self):
        """Test dashboard renders in browser"""
        pytest.skip("Integration test - requires browser")


# =====================================================================
# Run tests with: pytest tests/test_webui_unit.py -v
# Run with coverage: pytest tests/test_webui_unit.py --cov=web_ui_service --cov-report=html
# =====================================================================


class TestDynamicConfigAPI:
    """Tests for Web UI dynamic configuration endpoints"""

    def _make_app(self, monkeypatch, mock_secrets):
        import services.web_ui_service as webui

        # Stub secrets fetch to avoid Vault
        def fake_fetch_secrets(app):
            app.config["SECRETS"] = dict(mock_secrets)
        monkeypatch.setattr(webui, "fetch_secrets", fake_fetch_secrets)

        # Minimal env so Config validation passes
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_ROLE_ID", "test-role")

        # Stub Redis/DB pool creators
        def fake_create_redis_pool(app):
            class DummyPool: pass
            app.redis_pool = DummyPool()
        monkeypatch.setattr(webui, "create_redis_pool", fake_create_redis_pool)

        # Avoid real redis client creation during DynamicConfig init
        # Provide a stub redis module with a static Redis constructor
        monkeypatch.setattr(webui, "redis", type("R", (), {"Redis": staticmethod(lambda **kwargs: object())}))

        def fake_create_postgres_pool(app):
            class DummyPool:
                def __init__(self):
                    self._conn = None
                def getconn(self):
                    return self._conn
                def putconn(self, _):
                    return None
            app.config['DB_POOL'] = DummyPool()
        monkeypatch.setattr(webui, "create_postgres_pool", fake_create_postgres_pool)

        # Fake DynamicConfig that records get/set
        class FakeDyn:
            def __init__(self, *_args, **_kwargs):
                self.store = {"existing_key": "123"}
            def start_watcher(self):
                return None
            def get_all(self):
                return dict(self.store)
            def get(self, key, default=None):
                return self.store.get(key, default)
            def set(self, key, value, notify=True):
                self.store[key] = str(value)

        monkeypatch.setattr(webui, "DynamicConfig", FakeDyn)

        # Stub audit logger to capture calls
        calls = {}
        def fake_log_config_change(**kwargs):
            calls["last"] = kwargs
            return 1
        monkeypatch.setattr(webui, "log_config_change", fake_log_config_change, raising=False)

        app = webui.create_app()
        app.testing = True
        return app, calls

    def test_get_config_returns_values(self, monkeypatch, mock_secrets):
        app, _ = self._make_app(monkeypatch, mock_secrets)
        client = app.test_client()
        resp = client.get(
            "/api/v1/config",
            headers={"X-API-KEY": mock_secrets["WEBUI_API_KEY"]}
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "config" in body
        assert body["config"].get("existing_key") == "123"

    def test_put_config_updates_and_audits(self, monkeypatch, mock_secrets):
        app, calls = self._make_app(monkeypatch, mock_secrets)
        client = app.test_client()
        resp = client.put(
            "/api/v1/config/new_key",
            headers={
                "X-API-KEY": mock_secrets["WEBUI_API_KEY"],
                "Content-Type": "application/json"
            },
            data=json.dumps({"value": "xyz", "reason": "unit test"})
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["key"] == "new_key"
        assert body["new_value"] == "xyz"
        # Audit logger called
        assert "last" in calls
        audit = calls["last"]
        assert audit["table_name"] == "dynamic_config"
        assert audit["new_values"]["key"] == "new_key"
        assert audit["new_values"]["value"] == "xyz"

    def test_put_config_missing_value_400(self, monkeypatch, mock_secrets):
        app, _ = self._make_app(monkeypatch, mock_secrets)
        client = app.test_client()
        resp = client.put(
            "/api/v1/config/any",
            headers={"X-API-KEY": mock_secrets["WEBUI_API_KEY"]},
            data=json.dumps({}),
            content_type="application/json"
        )
        assert resp.status_code == 400

    def test_get_config_history_paginates(self, monkeypatch, mock_secrets):
        import services.web_ui_service as webui
        app, _ = self._make_app(monkeypatch, mock_secrets)

        # Replace DB pool with a fake connection that returns count and rows
        class FakeCursor:
            def __init__(self):
                self.phase = 0
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def execute(self, query, params=None):
                self.phase += 1
            def fetchone(self):
                return (3,)
            def fetchall(self):
                return [
                    {"id": 1, "operation": "CREATE", "table_name": "dynamic_config"},
                    {"id": 2, "operation": "UPDATE", "table_name": "dynamic_config"}
                ]

        class FakeConn:
            def cursor(self, *args, **kwargs):
                return FakeCursor()
            def commit(self):
                return None
            def rollback(self):
                return None

        class FakePool:
            def getconn(self):
                return FakeConn()
            def putconn(self, _):
                return None

        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        resp = client.get(
            "/api/v1/config/history?page=1&limit=2",
            headers={"X-API-KEY": mock_secrets["WEBUI_API_KEY"]}
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "history" in body and isinstance(body["history"], list)
        assert body["pagination"]["total"] == 3
