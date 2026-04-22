"""Tests for config validation integration in connector factory."""

import pytest
from connectors import get_connector
from connectors.jira import JiraConnector
from connectors.csv_connector import CSVConnector


class TestGetConnectorValidation:
    """Test that get_connector validates configs before instantiation."""
    
    def test_valid_jira_config(self):
        """Should instantiate Jira connector with valid config."""
        config = {
            "jira_url": "https://company.atlassian.net",
            "username": "user@company.com",
            "api_token": "token"
        }
        connector = get_connector("jira", config, [])
        assert isinstance(connector, JiraConnector)
    
    def test_jira_missing_required_field(self):
        """Should raise ValueError for missing required field."""
        config = {
            "jira_url": "https://company.atlassian.net",
            "username": "user@company.com"
            # missing api_token
        }
        with pytest.raises(ValueError) as exc:
            get_connector("jira", config, [])
        # Error should mention missing token or auth
        assert "api_token" in str(exc.value).lower() or "token" in str(exc.value).lower()
    
    def test_jira_invalid_url(self):
        """Should raise ValueError for invalid URL."""
        config = {
            "jira_url": "invalid-url",  # missing protocol
            "username": "user@company.com",
            "api_token": "token"
        }
        with pytest.raises(ValueError) as exc:
            get_connector("jira", config, [])
        assert "http" in str(exc.value).lower()
    
    def test_valid_csv_config(self):
        """Should instantiate CSV connector with valid config."""
        config = {
            "file_path": "/path/to/file.csv"
        }
        connector = get_connector("csv", config, [])
        assert isinstance(connector, CSVConnector)
    
    def test_csv_file_size_bounds(self):
        """Should validate CSV file size bounds."""
        config = {
            "file_path": "/path/to/file.csv",
            "max_file_size_mb": 1001  # exceeds max of 500
        }
        with pytest.raises(ValueError) as exc:
            get_connector("csv", config, [])
        assert "file_size" in str(exc.value).lower() or "500" in str(exc.value)
    
    def test_unknown_platform(self):
        """Should raise ValueError for unknown platform."""
        with pytest.raises(ValueError) as exc:
            get_connector("unknown_platform", {}, [])
        assert "unknown platform" in str(exc.value).lower()
    
    def test_valid_trello_config(self):
        """Should instantiate Trello connector with valid config."""
        config = {
            "api_key": "key123",
            "api_token": "token456",
            "board_id": "board789"
        }
        connector = get_connector("trello", config, [])
        assert connector is not None
    
    def test_validated_config_passed_to_connector(self):
        """Should pass validated config (not original) to connector."""
        # Jira config with trailing slash (should be normalized)
        config = {
            "jira_url": "https://company.atlassian.net/",  # trailing slash
            "username": "user@company.com",
            "api_token": "token"
        }
        connector = get_connector("jira", config, [])
        # Connector should have normalized URL without trailing slash
        assert connector.config["jira_url"] == "https://company.atlassian.net"
