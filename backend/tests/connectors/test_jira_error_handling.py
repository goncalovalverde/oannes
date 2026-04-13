"""Tests for connector error handling with user-friendly messages."""
import pytest
from unittest.mock import Mock, patch
from jira import JIRAError


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


def test_fetch_items_handles_api_error_gracefully():
    """Fetch items should handle API errors and provide context."""
    from connectors.jira import JiraConnector
    
    connector = JiraConnector({
        'url': 'https://jira.example.com',
        'email': 'user@example.com',
        'api_token': 'token',
        'project_key': 'TEST'
    }, [{'display_name': 'To Do', 'stage': 'queue'}])
    
    with patch('jira.JIRA') as mock_jira_class:
        mock_jira = Mock()
        mock_jira_class.return_value = mock_jira
        mock_jira.search_issues.side_effect = JIRAError(
            status_code=401,
            text='Unauthorized'
        )
        
        with pytest.raises(JIRAError):  # Should not swallow the error, but API should handle it
            connector.fetch_items()
