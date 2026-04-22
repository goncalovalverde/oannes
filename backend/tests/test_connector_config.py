"""Tests for connector configuration validation."""

import pytest
from models.connector_config import (
    JiraConfig, CSVConfig, TrelloConfig, AzureDevOpsConfig,
    GitLabConfig, LinearConfig, ShortcutConfig,
    validate_connector_config, AuthTypeEnum
)
from pydantic import ValidationError


class TestJiraConfig:
    """Test Jira configuration validation."""
    
    def test_minimal_jira_config(self):
        """Minimal valid Jira config with API token auth."""
        config = JiraConfig(
            jira_url="https://company.atlassian.net",
            username="user@company.com",
            api_token="my-secret-token"
        )
        assert config.jira_url == "https://company.atlassian.net"
        assert config.auth_type == "api_token"
        assert config.request_delay_ms == 100
    
    def test_jira_url_trailing_slash_removed(self):
        """Trailing slash should be removed from Jira URL."""
        config = JiraConfig(
            jira_url="https://company.atlassian.net/",
            username="user@company.com",
            api_token="token"
        )
        assert config.jira_url == "https://company.atlassian.net"
    
    def test_jira_url_must_have_protocol(self):
        """Jira URL must start with http:// or https://."""
        with pytest.raises(ValidationError) as exc:
            JiraConfig(
                jira_url="company.atlassian.net",
                username="user@company.com",
                api_token="token"
            )
        assert "http://" in str(exc.value).lower() or "https://" in str(exc.value).lower()
    
    def test_personal_access_token_auth(self):
        """Should accept personal access token auth type."""
        config = JiraConfig(
            jira_url="https://company.atlassian.net",
            username="user@company.com",
            personal_access_token="pat-token",
            auth_type=AuthTypeEnum.PERSONAL_ACCESS_TOKEN
        )
        assert config.auth_type == "personal_access_token"
        assert config.personal_access_token == "pat-token"
    
    def test_api_token_required_for_api_token_auth(self):
        """api_token is required when auth_type is api_token."""
        with pytest.raises(ValidationError) as exc:
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                auth_type=AuthTypeEnum.API_TOKEN
            )
        assert "api_token" in str(exc.value).lower()
    
    def test_pat_required_for_pat_auth(self):
        """personal_access_token is required when auth_type is personal_access_token."""
        with pytest.raises(ValidationError) as exc:
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                auth_type=AuthTypeEnum.PERSONAL_ACCESS_TOKEN
            )
        assert "personal_access_token" in str(exc.value).lower()
    
    def test_request_delay_bounds(self):
        """request_delay_ms must be 0-5000."""
        # Valid: 0ms
        config = JiraConfig(
            jira_url="https://company.atlassian.net",
            username="user@company.com",
            api_token="token",
            request_delay_ms=0
        )
        assert config.request_delay_ms == 0
        
        # Valid: 5000ms
        config = JiraConfig(
            jira_url="https://company.atlassian.net",
            username="user@company.com",
            api_token="token",
            request_delay_ms=5000
        )
        assert config.request_delay_ms == 5000
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                api_token="token",
                request_delay_ms=-1
            )
        
        # Invalid: over 5000
        with pytest.raises(ValidationError):
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                api_token="token",
                request_delay_ms=5001
            )


class TestCSVConfig:
    """Test CSV configuration validation."""
    
    def test_minimal_csv_config(self):
        """Minimal valid CSV config."""
        config = CSVConfig(file_path="/path/to/file.csv")
        assert config.file_path == "/path/to/file.csv"
        assert config.delimiter == ","
        assert config.has_header is True
        assert config.encoding == "utf-8"
        assert config.max_file_size_mb == 100
    
    def test_custom_delimiter(self):
        """Should support custom delimiters."""
        config = CSVConfig(
            file_path="/path/to/file.csv",
            delimiter=";"
        )
        assert config.delimiter == ";"
    
    def test_max_file_size_bounds(self):
        """max_file_size_mb must be 1-500."""
        # Valid: 1MB
        config = CSVConfig(
            file_path="/path/to/file.csv",
            max_file_size_mb=1
        )
        assert config.max_file_size_mb == 1
        
        # Valid: 500MB
        config = CSVConfig(
            file_path="/path/to/file.csv",
            max_file_size_mb=500
        )
        assert config.max_file_size_mb == 500
        
        # Invalid: 0MB
        with pytest.raises(ValidationError):
            CSVConfig(
                file_path="/path/to/file.csv",
                max_file_size_mb=0
            )
        
        # Invalid: 501MB
        with pytest.raises(ValidationError):
            CSVConfig(
                file_path="/path/to/file.csv",
                max_file_size_mb=501
            )


class TestValidateConnectorConfig:
    """Test validate_connector_config function."""
    
    def test_validate_jira_config(self):
        """Should validate Jira config through helper function."""
        config = {
            "jira_url": "https://company.atlassian.net",
            "username": "user@company.com",
            "api_token": "token"
        }
        result = validate_connector_config("jira", config)
        assert result["jira_url"] == "https://company.atlassian.net"
        assert result["auth_type"] == "api_token"
    
    def test_validate_csv_config(self):
        """Should validate CSV config through helper function."""
        config = {
            "file_path": "/path/to/file.csv",
            "delimiter": ";"
        }
        result = validate_connector_config("csv", config)
        assert result["file_path"] == "/path/to/file.csv"
        assert result["delimiter"] == ";"
    
    def test_unknown_connector_type(self):
        """Should raise error for unknown connector type."""
        with pytest.raises(ValueError) as exc:
            validate_connector_config("unknown", {})
        assert "unknown connector type" in str(exc.value).lower()
    
    def test_invalid_config_raises_valueerror(self):
        """Should raise ValueError for invalid config."""
        config = {
            "jira_url": "invalid-url",
            "username": "user@company.com"
        }
        with pytest.raises(ValueError) as exc:
            validate_connector_config("jira", config)
        assert "invalid" in str(exc.value).lower() or "http" in str(exc.value).lower()


class TestTrelloConfig:
    """Test Trello configuration validation."""
    
    def test_minimal_trello_config(self):
        """Minimal valid Trello config."""
        config = TrelloConfig(
            api_key="key123",
            api_token="token456",
            board_id="board789"
        )
        assert config.api_key == "key123"
        assert config.api_token == "token456"
        assert config.board_id == "board789"


class TestAzureDevOpsConfig:
    """Test Azure DevOps configuration validation."""
    
    def test_minimal_azure_config(self):
        """Minimal valid Azure DevOps config."""
        config = AzureDevOpsConfig(
            organization="my-org",
            project="my-project",
            pat="pat-token"
        )
        assert config.organization == "my-org"
        assert config.project == "my-project"
        assert config.pat == "pat-token"


class TestGitLabConfig:
    """Test GitLab configuration validation."""
    
    def test_minimal_gitlab_config(self):
        """Minimal valid GitLab config."""
        config = GitLabConfig(
            gitlab_url="https://gitlab.company.com",
            project_id="123",
            private_token="token"
        )
        assert config.gitlab_url == "https://gitlab.company.com"
    
    def test_gitlab_url_trailing_slash_removed(self):
        """Trailing slash should be removed from GitLab URL."""
        config = GitLabConfig(
            gitlab_url="https://gitlab.company.com/",
            project_id="123",
            private_token="token"
        )
        assert config.gitlab_url == "https://gitlab.company.com"


class TestLinearConfig:
    """Test Linear configuration validation."""
    
    def test_minimal_linear_config(self):
        """Minimal valid Linear config."""
        config = LinearConfig(api_key="api-key")
        assert config.api_key == "api-key"
        assert config.team_id is None


class TestShortcutConfig:
    """Test Shortcut configuration validation."""
    
    def test_minimal_shortcut_config(self):
        """Minimal valid Shortcut config."""
        config = ShortcutConfig(
            api_token="token",
            workflow_id="workflow123"
        )
        assert config.api_token == "token"
        assert config.workflow_id == "workflow123"
