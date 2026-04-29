"""Pydantic models for validating connector configurations.

Each connector has specific required and optional fields. These models provide:
- Type validation
- Required field validation
- Clear error messages for misconfiguration
- Default values where applicable
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal

class JiraConfig(BaseModel):
    """Validates Jira connector configuration.
    
    Required:
    - jira_url: Jira instance URL (e.g., https://company.atlassian.net)
    - username: User email or username
    - api_token: API token (if auth_type is api_token) or
    - personal_access_token: Personal access token (if auth_type is personal_access_token)
    
    Optional:
    - auth_type: "api_token" or "personal_access_token" (default: "api_token")
    - project_key: Jira project key (e.g., "PROJ")
    - jql: Custom JQL for filtering issues
    - api_version: "v2" (Server/Data Center) or "v3" (Cloud) (default: "v2")
    - request_delay_ms: Delay between requests in milliseconds (default: 100)
    - max_retries: Maximum retries on rate limit (default: 3)
    """
    
    jira_url: Optional[str] = Field(
        None, 
        description="Jira instance URL"
    )
    username: Optional[str] = Field(
        None,
        description="Jira username or email"
    )
    api_token: Optional[str] = Field(
        None,
        description="API token (for api_token auth type)"
    )
    personal_access_token: Optional[str] = Field(
        None,
        description="Personal access token (for personal_access_token auth type)"
    )
    auth_type: Literal["api_token", "personal_access_token", "oauth"] = Field(
        "api_token",
        description="Authentication type"
    )
    project_key: Optional[str] = Field(
        None,
        description="Jira project key"
    )
    jql: Optional[str] = Field(
        None,
        description="Custom JQL query for filtering issues"
    )
    api_version: Literal["v2", "v3"] = Field(
        "v2",
        description="Jira REST API version to use: 'v2' (Server/Data Center) or 'v3' (Cloud)"
    )
    request_delay_ms: int = Field(
        100,
        ge=0,
        le=5000,
        description="Delay between requests (0-5000ms)"
    )
    max_retries: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum retries on rate limit (1-10)"
    )
    
    @field_validator('jira_url')
    @classmethod
    def validate_jira_url(cls, v):
        """Ensure URL is properly formatted."""
        if not v:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError('jira_url must start with http:// or https://')
        if v.endswith('/'):
            return v[:-1]  # Remove trailing slash
        return v

    @model_validator(mode='after')
    def validate_required_and_auth_token(self):
        """Ensure required fields are present and appropriate auth token is provided.
        
        For API token auth: requires jira_url, username, and api_token
        For PAT auth: requires jira_url and personal_access_token (username not needed)
        """
        # jira_url is always required
        if not self.jira_url:
            raise ValueError('jira_url is required')
        
        # Validate auth-specific requirements
        if self.auth_type == "api_token":
            if not self.username:
                raise ValueError('username is required when auth_type is "api_token"')
            if not self.api_token:
                raise ValueError('api_token is required when auth_type is "api_token"')
        elif self.auth_type == "personal_access_token":
            if not self.personal_access_token:
                raise ValueError('personal_access_token is required when auth_type is "personal_access_token"')
        
        return self
    
    class Config:
        use_enum_values = True


class CSVConfig(BaseModel):
    """Validates CSV connector configuration.

    CSV projects use in-memory file upload (POST /api/sync/{id}/csv-upload).
    All fields are optional — an empty config dict is valid for project creation.

    Optional:
    - delimiter: CSV delimiter (default: ",")
    - has_header: Whether CSV has header row (default: true)
    - encoding: File encoding (default: "utf-8")
    - max_file_size_mb: Maximum file size in MB (default: 100)
    - date_columns: List of columns to parse as dates
    - status_column: Column name for status
    - date_column: Column name for dates
    """

    delimiter: str = Field(
        ",",
        description="CSV delimiter character"
    )
    has_header: bool = Field(
        True,
        description="Whether CSV has header row"
    )
    encoding: str = Field(
        "utf-8",
        description="File encoding"
    )
    max_file_size_mb: int = Field(
        100,
        ge=1,
        le=500,
        description="Maximum file size (1-500 MB)"
    )
    date_columns: List[str] = Field(
        default_factory=list,
        description="Column names to parse as dates"
    )
    status_column: Optional[str] = Field(
        None,
        description="Column name for status"
    )
    date_column: Optional[str] = Field(
        None,
        description="Column name for dates"
    )


class TrelloConfig(BaseModel):
    """Validates Trello connector configuration.
    
    Required:
    - api_key: Trello API key
    - token: Trello API token
    - project_key: Trello board ID
    
    Optional:
    - max_retries: Maximum retries on rate limit (default: 3)
    """
    
    api_key: Optional[str] = Field(
        None,
        description="Trello API key"
    )
    token: Optional[str] = Field(
        None,
        description="Trello API token"
    )
    project_key: Optional[str] = Field(
        None,
        description="Trello board ID"
    )
    max_retries: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum retries on rate limit (1-10)"
    )
    
    @model_validator(mode='after')
    def validate_required_fields(self):
        """Ensure all required fields are present."""
        if not self.api_key:
            raise ValueError('api_key is required')
        if not self.token:
            raise ValueError('token is required')
        if not self.project_key:
            raise ValueError('project_key is required')
        return self


class AzureDevOpsConfig(BaseModel):
    """Validates Azure DevOps connector configuration.
    
    Required:
    - org_url: Azure DevOps organization URL (e.g., https://dev.azure.com/yourorg)
    - personal_access_token: Personal access token
    - project_key: Project name
    
    Optional:
    - max_retries: Maximum retries on rate limit (default: 3)
    """
    
    org_url: Optional[str] = Field(
        None,
        description="Azure DevOps organization URL"
    )
    personal_access_token: Optional[str] = Field(
        None,
        description="Personal access token"
    )
    project_key: Optional[str] = Field(
        None,
        description="Project name"
    )
    max_retries: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum retries on rate limit (1-10)"
    )
    
    @model_validator(mode='after')
    def validate_required_fields(self):
        """Ensure all required fields are present."""
        if not self.org_url:
            raise ValueError('org_url is required')
        if not self.personal_access_token:
            raise ValueError('personal_access_token is required')
        if not self.project_key:
            raise ValueError('project_key is required')
        return self


class GitLabConfig(BaseModel):
    """Validates GitLab connector configuration.
    
    Required:
    - url: GitLab instance URL
    - access_token: Private access token
    - project_key: Project ID
    
    Optional:
    - max_retries: Maximum retries on rate limit (default: 3)
    """
    
    url: Optional[str] = Field(
        None,
        description="GitLab instance URL"
    )
    project_key: Optional[str] = Field(
        None,
        description="Project ID"
    )
    access_token: Optional[str] = Field(
        None,
        description="Private access token"
    )
    max_retries: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum retries on rate limit (1-10)"
    )
    
    @field_validator('url')
    @classmethod
    def validate_gitlab_url(cls, v):
        """Ensure URL is properly formatted."""
        if not v:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError('url must start with http:// or https://')
        if v.endswith('/'):
            return v[:-1]
        return v
    
    @model_validator(mode='after')
    def validate_required_fields(self):
        """Ensure all required fields are present."""
        if not self.url:
            raise ValueError('url is required')
        if not self.project_key:
            raise ValueError('project_key is required')
        if not self.access_token:
            raise ValueError('access_token is required')
        return self


class LinearConfig(BaseModel):
    """Validates Linear connector configuration.
    
    Required:
    - api_key: Linear API key
    - team_id: Linear team ID (optional, if filtering by team)
    
    Optional:
    - max_retries: Maximum retries on rate limit (default: 3)
    """
    
    api_key: str = Field(
        ...,
        description="Linear API key"
    )
    team_id: Optional[str] = Field(
        None,
        description="Linear team ID"
    )
    max_retries: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum retries on rate limit (1-10)"
    )


class ShortcutConfig(BaseModel):
    """Validates Shortcut connector configuration.
    
    Required:
    - api_token: Shortcut API token
    - workflow_id: Shortcut workflow ID
    
    Optional:
    - max_retries: Maximum retries on rate limit (default: 3)
    """
    
    api_token: str = Field(
        ...,
        description="Shortcut API token"
    )
    workflow_id: str = Field(
        ...,
        description="Shortcut workflow ID"
    )
    max_retries: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum retries on rate limit (1-10)"
    )


def validate_connector_config(connector_type: str, config: dict) -> dict:
    """Validate connector configuration and return validated config.
    
    Args:
        connector_type: Type of connector (jira, csv, trello, etc.)
        config: Configuration dictionary
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid
    """
    connector_validators = {
        'jira': JiraConfig,
        'csv': CSVConfig,
        'trello': TrelloConfig,
        'azure_devops': AzureDevOpsConfig,
        'gitlab': GitLabConfig,
        'linear': LinearConfig,
        'shortcut': ShortcutConfig,
    }
    
    if connector_type not in connector_validators:
        raise ValueError(f"Unknown connector type: {connector_type}")
    
    validator_class = connector_validators[connector_type]
    
    try:
        validated = validator_class(**config)
        return validated.dict()
    except Exception as e:
        raise ValueError(f"Invalid {connector_type} configuration: {str(e)}")
