"""Tests for Jira automatic rate limit retry handling."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from jira import JIRAError

from connectors.jira import JiraConnector


@pytest.fixture
def jira_connector():
    """Create a JiraConnector instance with minimal config."""
    return JiraConnector(
        config={
            "url": "https://test.atlassian.net",
            "auth_type": "api_token",
            "email": "test@example.com",
            "api_token": "test_token",
            "project_key": "TEST",
            "jira_api_version": "v2",
        },
        workflow_steps=[
            {"stage": "queue", "source_statuses": ["New"]},
            {"stage": "in_flight", "source_statuses": ["In Progress"]},
            {"stage": "done", "source_statuses": ["Done"]},
        ],
    )


def test_retry_succeeds_after_429_error(jira_connector):
    """_retry_with_rate_limit_backoff should succeed after transient 429 error."""
    call_count = 0
    
    def mock_func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call fails with 429
            raise JIRAError(status_code=429, text="Rate limit exceeded")
        else:
            # Second call succeeds
            return {"success": True}
    
    with patch('time.sleep'):  # Mock sleep to avoid delays in tests
        result = jira_connector._retry_with_rate_limit_backoff(mock_func)
    
    assert result == {"success": True}
    assert call_count == 2


def test_retry_exhausts_after_max_retries(jira_connector):
    """_retry_with_rate_limit_backoff should raise after exhausting retries."""
    def mock_func():
        # Always fail with 429
        raise JIRAError(status_code=429, text="Rate limit exceeded")
    
    with patch('time.sleep'):  # Mock sleep to avoid delays
        with pytest.raises(JIRAError) as exc_info:
            jira_connector._retry_with_rate_limit_backoff(mock_func, max_retries=2)
    
    assert exc_info.value.status_code == 429


def test_retry_applies_exponential_backoff(jira_connector):
    """_retry_with_rate_limit_backoff should use exponential backoff times."""
    call_count = 0
    
    def mock_func():
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            # Fail 3 times with error message that has no "after X seconds"
            raise JIRAError(status_code=429, text="Rate limit exceeded. Please try again later.")
        else:
            # Succeed on 4th try
            return {"success": True}
    
    with patch('time.sleep') as mock_sleep:
        result = jira_connector._retry_with_rate_limit_backoff(mock_func, max_retries=3)
    
    assert result == {"success": True}
    # Sleep should be called 3 times with exponential backoff: 6, 7, 9 seconds
    # Formula: 5 + 2^attempt where attempt is 0-indexed
    assert mock_sleep.call_count == 3
    sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
    assert sleep_times[0] == 6  # 5 + 2^0
    assert sleep_times[1] == 7  # 5 + 2^1
    assert sleep_times[2] == 9  # 5 + 2^2


def test_retry_does_not_retry_non_429_errors(jira_connector):
    """_retry_with_rate_limit_backoff should NOT retry non-429 errors."""
    def mock_func():
        # Fail with 401 (not 429)
        raise JIRAError(status_code=401, text="Unauthorized")
    
    with pytest.raises(JIRAError) as exc_info:
        jira_connector._retry_with_rate_limit_backoff(mock_func, max_retries=3)
    
    assert exc_info.value.status_code == 401


def test_retry_extracts_retry_after_from_error_message(jira_connector):
    """_retry_with_rate_limit_backoff should extract Retry-After from error message."""
    call_count = 0
    
    def mock_func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Error message contains "after 10 seconds"
            raise JIRAError(status_code=429, text="Rate limit exceeded. Request should be retried after 10 seconds.")
        else:
            return {"success": True}
    
    with patch('time.sleep') as mock_sleep:
        result = jira_connector._retry_with_rate_limit_backoff(mock_func)
    
    assert result == {"success": True}
    # Should extract 10 from error message, not use default backoff
    mock_sleep.assert_called_once_with(10)


def test_fetch_all_issues_retries_on_429(jira_connector):
    """fetch_all_issues should retry on 429 rate limit errors."""
    call_count = 0
    
    def mock_search(jql, start, batch):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call fails
            raise JIRAError(status_code=429, text="Rate limit exceeded. Request should be retried after 5 seconds.")
        else:
            # Second call succeeds
            return {"issues": [{"key": "TEST-1"}, {"key": "TEST-2"}]}
    
    with patch('time.sleep'):  # Mock sleep to avoid delays
        result = jira_connector._fetch_all_issues(mock_search, "project = TEST")
    
    assert len(result) == 2
    assert result[0]["key"] == "TEST-1"
    assert call_count == 2
