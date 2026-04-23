"""Tests for Jira v2/v3 API fallback and version detection."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from jira import JIRAError
import pandas as pd
from models.connector_config import validate_connector_config


def normalize_jira_config(config: dict) -> dict:
    """Normalize frontend field names to backend field names using Pydantic validation.
    
    This ensures tests use the same normalized config that production code receives
    from validate_connector_config().
    """
    return validate_connector_config('jira', config)


class TestJiraApiVersionResolution:
    """Test _resolve_api_version() method."""

    def test_auto_detect_v3_success(self):
        """Auto-detect should return v3 when v3 endpoint succeeds."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token',
            'jira_api_version': 'auto'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            result = connector._resolve_api_version()

            assert result == "v3"
            # Verify that v3 endpoint was tested
            called_url = mock_session.get.call_args[0][0]
            assert '/rest/api/3/myself' in called_url

    def test_auto_detect_v3_404_fallback_to_v2(self):
        """Auto-detect should fallback to v2 when v3 returns 404."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token',
            'jira_api_version': 'auto'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.status_code = 404
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            result = connector._resolve_api_version()

            assert result == "v2"

    def test_force_v3_skips_detection(self):
        """Explicitly set v3 should skip auto-detect."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token',
            'jira_api_version': 'v3'
        }), [])

        result = connector._resolve_api_version()

        assert result == "v3"

    def test_force_v2_skips_detection(self):
        """Explicitly set v2 should skip auto-detect."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token',
            'jira_api_version': 'v2'
        }), [])

        result = connector._resolve_api_version()

        assert result == "v2"

    def test_auto_detect_auth_error_reraises(self):
        """Auto-detect should re-raise auth errors (401/403), not assume v2."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'bad_token',
            'jira_api_version': 'auto'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira_class.side_effect = JIRAError(status_code=401, text='Unauthorized')

            with pytest.raises(JIRAError) as exc_info:
                connector._resolve_api_version()

            assert exc_info.value.status_code == 401

    def test_default_version_is_auto(self):
        """Default jira_api_version should be 'auto' when not specified."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token'
            # No jira_api_version specified
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            result = connector._resolve_api_version()

            # Should default to auto-detect and return v3
            assert result == "v3"


class TestJiraV2Search:
    """Test _search_issues_v2() method."""

    def test_search_v2_returns_issues(self):
        """v2 search should call /rest/api/2/search and return issues."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token'
        }), [])

        v2_response = {
            "issues": [
                {
                    "key": "TEST-1",
                    "fields": {
                        "issuetype": {"name": "Story"},
                        "creator": {"displayName": "Alice"},
                        "created": "2026-01-01T10:00:00.000+0000"
                    },
                    "changelog": {"histories": []}
                }
            ],
            "total": 1
        }

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = v2_response
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            result = connector._search_issues_v2("project = TEST", 0, 100)

            assert len(result["issues"]) == 1
            assert result["issues"][0]["key"] == "TEST-1"
            # Verify v2 endpoint was called
            called_url = mock_session.get.call_args[0][0]
            assert '/rest/api/2/search' in called_url

    def test_search_v2_pagination(self):
        """v2 search should pass startAt and maxResults params."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"issues": [], "total": 0}
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            connector._search_issues_v2("project = TEST", 100, 50)

            # Verify pagination params
            call_args = mock_session.get.call_args
            assert call_args[1]["params"]["startAt"] == 100
            assert call_args[1]["params"]["maxResults"] == 50


class TestJiraFetchItemsVersionSelection:
    """Test fetch_items() version selection and caching."""

    def test_fetch_items_resolves_version_once(self):
        """fetch_items should resolve API version once and reuse for all batches."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token',
            'project_key': 'TEST',
            'jira_api_version': 'v3'
        }), [
            {'display_name': 'Done', 'stage': 'done', 'source_statuses': ['Done']}
        ])

        response = {
            "issues": [
                {
                    "key": "TEST-1",
                    "fields": {
                        "issuetype": {"name": "Story"},
                        "creator": {"displayName": "Alice"},
                        "created": "2026-01-01T10:00:00.000+0000"
                    },
                    "changelog": {"histories": []}
                }
            ],
            "total": 1
        }

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = response
            mock_resp.headers = {}  # Real dict for headers
            mock_session.headers = {}  # Real dict for session headers
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            df = connector.fetch_items()

            assert len(df) == 1
            # Verify only one search method was called (not both v2 and v3)
            search_calls = [call for call in mock_session.get.call_args_list
                          if '/search' in call[0][0]]
            assert len(search_calls) == 1

    def test_fetch_items_uses_v2_when_forced(self):
        """fetch_items should use v2 API when explicitly set."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'email': 'user@example.com',
            'api_token': 'token',
            'project_key': 'TEST',
            'jira_api_version': 'v2'
        }), [
            {'display_name': 'Done', 'stage': 'done', 'source_statuses': ['Done']}
        ])

        response = {
            "issues": [],
            "total": 0
        }

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            mock_resp = Mock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = response
            mock_session.get.return_value = mock_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            df = connector.fetch_items()

            # Verify v2 endpoint was called
            called_url = [call[0][0] for call in mock_session.get.call_args_list
                         if '/search' in call[0][0]][0]
            assert '/rest/api/2/search' in called_url


class TestJiraTestConnectionVersionDetection:
    """Test test_connection() API version detection."""

    def test_test_connection_returns_api_version_detected_v3(self):
        """test_connection should return api_version_detected=v3 when v3 works."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'auth_type': 'api_token',
            'email': 'user@example.com',
            'api_token': 'token',
            'jira_api_version': 'auto'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_session = Mock()
            
            # Mock responses for all v3 calls:
            # 1. Auto-detect myself call
            # 2. Test v3 myself endpoint
            # 3. Test v3 projects endpoint
            v3_resp = Mock()
            v3_resp.raise_for_status.return_value = None
            v3_resp.status_code = 200
            v3_resp.json.side_effect = [
                {"displayName": "Test User"},  # Auto-detect myself
                {"displayName": "Test User"},  # Test myself
                {"values": [{"key": "PROJ1", "name": "Project 1"}]}  # Test projects
            ]
            
            mock_session.get.return_value = v3_resp
            mock_jira._session = mock_session
            mock_jira_class.return_value = mock_jira

            result = connector.test_connection()

            assert result['success'] is True
            assert result['api_version_detected'] == 'v3'
            assert 'API v3' in result['message']

    def test_test_connection_returns_api_version_detected_v2(self):
        """test_connection should return api_version_detected=v2 when forced v2."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'auth_type': 'api_token',
            'email': 'user@example.com',
            'api_token': 'token',
            'jira_api_version': 'v2'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira = Mock()
            mock_jira.projects.return_value = [
                Mock(key='PROJ1', name='Project 1')
            ]
            mock_jira_class.return_value = mock_jira

            result = connector.test_connection()

            assert result['success'] is True
            assert result['api_version_detected'] == 'v2'
            assert 'API v2' in result['message']

    def test_test_connection_failure_includes_api_version_detected_none(self):
        """test_connection failure should include api_version_detected=None."""
        from connectors.jira import JiraConnector

        connector = JiraConnector(normalize_jira_config({
            'url': 'https://jira.example.com',
            'auth_type': 'api_token',
            'email': 'bad@example.com',
            'api_token': 'bad_token',
            'jira_api_version': 'auto'
        }), [])

        with patch('jira.JIRA') as mock_jira_class:
            mock_jira_class.side_effect = JIRAError(status_code=401, text='Unauthorized')

            result = connector.test_connection()

            assert result['success'] is False
            assert result['api_version_detected'] is None


class TestJiraErrorMessagesV2Suggestion:
    """Test that error messages suggest v2 when appropriate."""

    def test_v3_404_error_suggests_v2(self):
        """404 on v3 search/jql should suggest v2 in error message."""
        from connectors.jira import _format_jira_error

        error = JIRAError(status_code=404, text='Not found')
        message = _format_jira_error(error, context='search/jql endpoint')

        assert 'v2' in message.lower() or 'older' in message.lower() or 'version' in message.lower()

    def test_api_removed_error_suggests_v2(self):
        """'API removed' error should suggest v2."""
        from connectors.jira import _format_jira_error

        error = Exception("The requested API has been removed. Please migrate to /rest/api/3/search/jql")
        message = _format_jira_error(error)

        assert 'v2' in message.lower() or 'older' in message.lower() or 'version' in message.lower()
