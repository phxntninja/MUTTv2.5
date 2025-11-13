#!/usr/bin/env python3
"""
MUTT v2.5 - API Versioning Integration Tests

Integration tests for API versioning functionality.

Run with:
    pytest tests/test_versioning_integration.py -v
"""

import pytest
import json
from unittest.mock import Mock, patch
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))


@pytest.fixture
def app(monkeypatch):
    """Fixture to create the Flask app once per test class."""
    from services.web_ui_service import create_app
    with patch('services.web_ui_service.fetch_secrets'), \
         patch('services.web_ui_service.create_redis_pool'), \
         patch('services.web_ui_service.create_postgres_pool'):

        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRETS'] = {'WEBUI_API_KEY': 'test-key'}
        yield app

@pytest.mark.usefixtures("app")
class TestVersionHeadersIntegration:
    """Integration tests for version headers on API responses"""

    def test_api_responses_include_version_headers(self, app):
        """Test that all API responses include version headers"""
        client = app.test_client()

        # Call version endpoint (no auth required)
        response = client.get('/api/v1/version')

        # Verify response has version headers
        assert response.status_code == 200
        assert 'X-API-Version' in response.headers
        assert 'X-API-Supported-Versions' in response.headers

    def test_version_endpoint_returns_comprehensive_info(self, app):
        """Test that version endpoint returns comprehensive version info"""
        client = app.test_client()

        response = client.get('/api/v1/version')
        assert response.status_code == 200

        data = json.loads(response.data)

        # Verify structure
        assert 'current_version' in data
        assert 'supported_versions' in data
        assert 'version_history' in data

        # Verify content
        assert isinstance(data['supported_versions'], list)
        assert len(data['supported_versions']) > 0
        assert data['current_version'] in data['supported_versions']

        # Verify version history has details
        assert isinstance(data['version_history'], dict)
        for version, info in data['version_history'].items():
            assert 'released' in info
            assert 'status' in info
            assert 'changes' in info


@pytest.mark.usefixtures("app")
class TestVersionNegotiation:
    """Integration tests for version negotiation"""

    def test_accept_version_header_negotiation(self, app):
        """Test version negotiation via Accept-Version header"""
        client = app.test_client()

        # Request with specific version
        response = client.get(
            '/api/v1/version',
            headers={'Accept-Version': '2.0'}
        )

        assert response.status_code == 200
        assert response.headers.get('X-API-Version') == '2.5'

    def test_x_api_version_header_negotiation(self, app):
        """Test version negotiation via X-API-Version header"""
        client = app.test_client()

        # Request with specific version
        response = client.get(
            '/api/v1/version',
            headers={'X-API-Version': '1.0'}
        )

        assert response.status_code == 200
        # Should still report current version in header
        assert 'X-API-Version' in response.headers

    def test_unsupported_version_falls_back_gracefully(self, app):
        """Test that unsupported version requests still work"""
        client = app.test_client()

        # Request with unsupported version
        response = client.get(
            '/api/v1/version',
            headers={'Accept-Version': '99.0'}
        )

        # Should still succeed (falls back to default)
        assert response.status_code == 200


@pytest.mark.usefixtures("app")
class TestVersionedEndpoints:
    """Integration tests for versioned endpoints"""

    def test_new_endpoint_has_version_metadata(self, app):
        """Test that new endpoints (since 2.0) indicate their version"""
        # Mock DB pool for audit endpoint
        mock_db_pool = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)  # No results
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [
            ('id',), ('changed_at',), ('changed_by',), ('operation',),
            ('table_name',), ('record_id',), ('old_values',), ('new_values',),
            ('reason',), ('correlation_id',)
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_db_pool.getconn.return_value = mock_conn
        app.config['DB_POOL'] = mock_db_pool

        client = app.test_client()

        # Call audit endpoint (new in 2.0)
        response = client.get(
            '/api/v1/audit',
            headers={'X-API-KEY': 'test-key'}
        )

        # Should have version headers
        assert 'X-API-Version' in response.headers


@pytest.mark.usefixtures("app")
class TestBackwardCompatibility:
    """Tests for backward compatibility support"""

    def test_v1_requests_still_work(self, app):
        """Test that v1 API requests still work"""
        client = app.test_client()

        # Request version info as v1 client
        response = client.get(
            '/api/v1/version',
            headers={'Accept-Version': '1.0'}
        )

        # Should work
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'current_version' in data
@pytest.mark.usefixtures("app")
class TestVersionDocumentation:
    """Tests for version documentation accuracy"""

    def test_version_history_is_complete(self, app):
        """Test that version history includes all supported versions"""
        client = app.test_client()

        response = client.get('/api/v1/version')
        data = json.loads(response.data)

        # All supported versions should be in history
        supported = data['supported_versions']
        history = data['version_history']

        for version in supported:
            assert version in history, f"Version {version} missing from history"

    def test_version_changelog_is_present(self, app):
        """Test that each version has a changelog"""
        client = app.test_client()

        response = client.get('/api/v1/version')
        data = json.loads(response.data)

        for version, info in data['version_history'].items():
            assert 'changes' in info, f"Version {version} missing changelog"
            assert len(info['changes']) > 0, f"Version {version} has empty changelog"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
