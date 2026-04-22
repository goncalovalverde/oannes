"""Tests for connector error handling with user-friendly messages."""
import pytest
from unittest.mock import Mock, patch
from jira import JIRAError
import json


def test_jira_401_unauthorized_returns_clear_message():
    """Jira 401 error should return actionable message about invalid credentials."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'wrong_token'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        # Simulate 401 error from Jira
        mock_jira.side_effect = JIRAError(
            status_code=401,
            text='Unauthorized'
        )
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'Invalid credentials' in result['message'] or 'credentials' in result['message'].lower()
        # Message should be actionable, not a raw stack trace


def test_jira_404_project_not_found_returns_clear_message():
    """Jira 404 error (project not found) should return actionable message."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'NONEXIST'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        mock_jira.side_effect = JIRAError(
            status_code=404,
            text='Project not found'
        )
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'not found' in result['message'].lower() or 'not found' in result['message']


def test_jira_403_forbidden_returns_clear_message():
    """Jira 403 error (permission denied) should return actionable message."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        mock_jira.side_effect = JIRAError(
            status_code=403,
            text='Forbidden'
        )
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'permission' in result['message'].lower()


def test_jira_connection_timeout_returns_clear_message():
    """Connection timeout should return actionable message about network/URL."""
    from connectors.jira import JiraConnector
    import socket
    
    connector = JiraConnector({
        'url': 'https://invalid.jira.url',
        'email': 'user@example.com',
        'api_token': 'token'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        mock_jira.side_effect = socket.timeout('Connection timed out')
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'timeout' in result['message'].lower() or 'url' in result['message'].lower()


def test_jira_json_parse_error_returns_clear_message():
    """JSON parsing error (malformed response) should suggest Jira URL or network issue."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        # Simulate JSON decode error (Expecting value: line 2 column 2)
        mock_jira.side_effect = json.JSONDecodeError('Expecting value', 'doc', 2)
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'invalid data' in result['message'].lower() or 'url' in result['message'].lower()


def test_jira_500_server_error_returns_clear_message():
    """Jira 500 server error should suggest waiting and retrying."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        mock_jira.side_effect = JIRAError(
            status_code=500,
            text='Internal Server Error'
        )
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'down' in result['message'].lower() or 'try again' in result['message'].lower()


def test_fetch_items_handles_api_error_gracefully():
    """Fetch items should handle API errors and provide context."""
    from connectors.jira import JiraConnector
    from requests.exceptions import HTTPError
    from unittest.mock import MagicMock
    import requests

    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'TEST'
    }, [{'display_name': 'To Do', 'stage': 'queue'}])

    with patch('connectors.jira.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = HTTPError(response=MagicMock(status_code=401))
        mock_get.return_value = mock_resp

        with pytest.raises(HTTPError):
            connector.fetch_items()


def test_fetch_items_uses_v3_api_endpoint():
    """fetch_items must call /rest/api/3/search/jql, never /rest/api/2/search."""
    from connectors.jira import JiraConnector
    from unittest.mock import MagicMock

    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'TEST'
    }, [{'display_name': 'Done', 'stage': 'done', 'source_statuses': ['Done']}])

    with patch('connectors.jira.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"issues": [], "total": 0}
        mock_get.return_value = mock_resp

        connector.fetch_items()

        called_url = mock_get.call_args[0][0]
        assert '/rest/api/3/search/jql' in called_url, (
            f"Expected v3 API endpoint but got: {called_url}"
        )
        assert '/rest/api/2/' not in called_url


def test_fetch_items_raises_on_jira_error_messages_in_200_response():
    """fetch_items should raise JIRAError when Jira returns errorMessages in a 200 body."""
    from connectors.jira import JiraConnector
    from unittest.mock import MagicMock

    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'TEST'
    }, [])

    with patch('connectors.jira.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "errorMessages": [
                "The requested API has been removed. Please migrate to the /rest/api/3/search/jql API."
            ],
            "errors": {}
        }
        mock_get.return_value = mock_resp

        with pytest.raises(JIRAError) as exc_info:
            connector.fetch_items()

        assert 'api/3' in str(exc_info.value).lower() or 'removed' in str(exc_info.value).lower()


def test_fetch_items_parses_v3_issue_structure():
    """fetch_items correctly extracts fields from Jira v3 JSON structure (dict, not objects)."""
    from connectors.jira import JiraConnector
    from unittest.mock import MagicMock

    steps = [
        {'display_name': 'In Progress', 'stage': 'start', 'source_statuses': ['in progress']},
        {'display_name': 'Done', 'stage': 'done', 'source_statuses': ['done']},
    ]
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'TEST'
    }, steps)

    v3_response = {
        "issues": [{
            "key": "TEST-1",
            "fields": {
                "issuetype": {"name": "Story"},
                "creator": {"displayName": "Alice"},
                "created": "2026-01-01T10:00:00.000+0000",
            },
            "changelog": {
                "histories": [
                    {
                        "created": "2026-01-02T10:00:00.000+0000",
                        "items": [{"field": "status", "toString": "In Progress"}]
                    },
                    {
                        "created": "2026-01-05T10:00:00.000+0000",
                        "items": [{"field": "status", "toString": "Done"}]
                    },
                ]
            }
        }],
        "total": 1
    }

    with patch('connectors.jira.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = v3_response
        mock_get.return_value = mock_resp

        df = connector.fetch_items()

        assert len(df) == 1
        assert df.iloc[0]['item_key'] == 'TEST-1'
        assert df.iloc[0]['item_type'] == 'Story'
        assert df.iloc[0]['cycle_time_days'] == 3  # Jan 2 → Jan 5


def test_jira_personal_access_token_auth():
    """JiraConnector should support Personal Access Token (Bearer) authentication."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'auth_type': 'personal_access_token',
        'personal_access_token': 'pat_token_12345'
    }, [{'display_name': 'Done', 'stage': 'done', 'source_statuses': ['done']}])
    
    with patch('jira.JIRA') as mock_jira_class:
        # Mock the JIRA client and its session
        mock_jira = Mock()
        mock_session = Mock()
        mock_session.headers = {}  # Real dict, not a mock
        mock_jira._session = mock_session
        mock_jira_class.return_value = mock_jira
        
        # Mock the response
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"issues": [], "total": 0}
        mock_session.get.return_value = mock_resp
        
        connector.fetch_items()
        
        # Verify session.get was called
        assert mock_session.get.called
        # Verify Bearer token is in session headers (set in _get_client)
        assert mock_session.headers.get('Authorization') == 'Bearer pat_token_12345'


def test_jira_api_token_auth_still_works():
    """JiraConnector should still support API Token (Basic Auth) authentication."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'auth_type': 'api_token',
        'email': 'user@example.com',
        'api_token': 'api_token_12345',
        'project_key': 'TEST'
    }, [{'display_name': 'Done', 'stage': 'done', 'source_statuses': ['done']}])
    
    with patch('jira.JIRA') as mock_jira_class:
        # Mock the JIRA client and its session
        mock_jira = Mock()
        mock_session = Mock()
        mock_jira._session = mock_session
        mock_jira_class.return_value = mock_jira
        
        # Mock the response
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"issues": [], "total": 0}
        mock_session.get.return_value = mock_resp
        
        connector.fetch_items()
        
        # Verify session.get was called
        assert mock_session.get.called


def test_jira_pat_test_connection():
    """test_connection should work with PAT authentication."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'auth_type': 'personal_access_token',
        'personal_access_token': 'pat_token'
    }, [])
    
    with patch('jira.JIRA') as mock_jira_class:
        mock_jira = Mock()
        mock_jira.projects.return_value = [
            Mock(key='PROJ1', name='Project 1'),
            Mock(key='PROJ2', name='Project 2')
        ]
        mock_jira_class.return_value = mock_jira
        
        result = connector.test_connection()
        
        assert result['success'] is True
        assert len(result['boards']) == 2
        assert result['boards'][0]['id'] == 'PROJ1'


def test_jira_429_rate_limit_returns_helpful_message():
    """Jira 429 rate limit error should return helpful message about request delay."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'TEST'
    }, [])
    
    with patch('jira.JIRA') as mock_jira:
        # Simulate 429 rate limit error from Jira
        mock_jira.side_effect = JIRAError(
            status_code=429,
            text='Rate limit exceeded'
        )
        
        result = connector.test_connection()
        
        assert result['success'] is False
        assert 'rate limit' in result['message'].lower()
        assert 'automatically retry' in result['message'].lower()
        assert 'request delay' in result['message'].lower()
        assert 'increase' in result['message'].lower()
