"""Tests for connector configuration validation."""

import pytest
from models.connector_config import (
    JiraConfig, CSVConfig, TrelloConfig, AzureDevOpsConfig,
    GitLabConfig, LinearConfig, ShortcutConfig,
    validate_connector_config,
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
            auth_type="personal_access_token"
        )
        assert config.auth_type == "personal_access_token"
        assert config.personal_access_token == "pat-token"
    
    def test_api_token_required_for_api_token_auth(self):
        """api_token is required when auth_type is api_token."""
        with pytest.raises(ValidationError) as exc:
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                auth_type="api_token"
            )
        assert "api_token" in str(exc.value).lower()
    
    def test_pat_required_for_pat_auth(self):
        """personal_access_token is required when auth_type is personal_access_token."""
        with pytest.raises(ValidationError) as exc:
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                auth_type="personal_access_token"
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

    def test_api_version_v2_accepted(self):
        """api_version 'v2' should be accepted."""
        config = JiraConfig(
            jira_url="https://company.atlassian.net",
            username="user@company.com",
            api_token="token",
            api_version="v2"
        )
        assert config.api_version == "v2"

    def test_api_version_v3_accepted(self):
        """api_version 'v3' should be accepted."""
        config = JiraConfig(
            jira_url="https://company.atlassian.net",
            username="user@company.com",
            api_token="token",
            api_version="v3"
        )
        assert config.api_version == "v3"

    def test_api_version_auto_rejected(self):
        """api_version 'auto' must be rejected — auto-detect was removed."""
        with pytest.raises(ValidationError) as exc:
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                api_token="token",
                api_version="auto"
            )
        assert "v2" in str(exc.value) or "v3" in str(exc.value)

    def test_api_version_invalid_string_rejected(self):
        """Any unknown api_version value must be rejected."""
        with pytest.raises(ValidationError):
            JiraConfig(
                jira_url="https://company.atlassian.net",
                username="user@company.com",
                api_token="token",
                api_version="v1"
            )


class TestCSVConfig:
    """Test CSV configuration validation."""
    
    def test_minimal_csv_config(self):
        """All fields optional — empty config is valid (upload flow)."""
        config = CSVConfig()
        assert config.delimiter == ","
        assert config.has_header is True
        assert config.encoding == "utf-8"
        assert config.max_file_size_mb == 100
    
    def test_custom_delimiter(self):
        """Should support custom delimiters."""
        config = CSVConfig(delimiter=";")
        assert config.delimiter == ";"
    
    def test_max_file_size_bounds(self):
        """max_file_size_mb must be 1-500."""
        assert CSVConfig(max_file_size_mb=1).max_file_size_mb == 1
        assert CSVConfig(max_file_size_mb=500).max_file_size_mb == 500

        with pytest.raises(ValidationError):
            CSVConfig(max_file_size_mb=0)

        with pytest.raises(ValidationError):
            CSVConfig(max_file_size_mb=501)


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
        result = validate_connector_config("csv", {"delimiter": ";"})
        assert result["delimiter"] == ";"

    def test_validate_csv_config_empty(self):
        """Empty CSV config (upload flow) must pass validation."""
        result = validate_connector_config("csv", {})
        assert result["delimiter"] == ","
    
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
            token="token456",
            project_key="board789"
        )
        assert config.api_key == "key123"
        assert config.token == "token456"
        assert config.project_key == "board789"


class TestAzureDevOpsConfig:
    """Test Azure DevOps configuration validation."""
    
    def test_minimal_azure_config(self):
        """Minimal valid Azure DevOps config."""
        config = AzureDevOpsConfig(
            org_url="https://dev.azure.com/my-org",
            personal_access_token="pat-token",
            project_key="my-project"
        )
        assert config.org_url == "https://dev.azure.com/my-org"
        assert config.personal_access_token == "pat-token"
        assert config.project_key == "my-project"


class TestGitLabConfig:
    """Test GitLab configuration validation."""
    
    def test_minimal_gitlab_config(self):
        """Minimal valid GitLab config."""
        config = GitLabConfig(
            url="https://gitlab.company.com",
            project_key="123",
            access_token="token"
        )
        assert config.url == "https://gitlab.company.com"
    
    def test_gitlab_url_trailing_slash_removed(self):
        """Trailing slash should be removed from GitLab URL."""
        config = GitLabConfig(
            url="https://gitlab.company.com/",
            project_key="123",
            access_token="token"
        )
        assert config.url == "https://gitlab.company.com"


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
