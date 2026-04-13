from fastapi import APIRouter
from pydantic import BaseModel, field_validator
from typing import List, Any, Optional, Dict, Literal, Union, Annotated
from connectors import get_connector

router = APIRouter()


# ---------------------------------------------------------------------------
# Per-platform config schemas
# ---------------------------------------------------------------------------

class JiraConfig(BaseModel):
    platform: Literal["jira"]
    url: str
    email: str
    api_token: str
    project_key: Optional[str] = None

class TrelloConfig(BaseModel):
    platform: Literal["trello"]
    api_key: str
    token: str
    board_id: Optional[str] = None

class AzureDevOpsConfig(BaseModel):
    platform: Literal["azure_devops"]
    organization: str
    project: str
    personal_access_token: str

class GitLabConfig(BaseModel):
    platform: Literal["gitlab"]
    url: str = "https://gitlab.com"
    private_token: str
    project_id: Optional[str] = None

class LinearConfig(BaseModel):
    platform: Literal["linear"]
    api_key: str
    team_id: Optional[str] = None

class ShortcutConfig(BaseModel):
    platform: Literal["shortcut"]
    api_token: str

class CSVConfig(BaseModel):
    platform: Literal["csv"]
    file_path: str

PlatformConfig = Annotated[
    Union[JiraConfig, TrelloConfig, AzureDevOpsConfig, GitLabConfig, LinearConfig, ShortcutConfig, CSVConfig],
    "discriminated by platform field"
]

_CONFIG_MODELS = {
    "jira": JiraConfig,
    "trello": TrelloConfig,
    "azure_devops": AzureDevOpsConfig,
    "gitlab": GitLabConfig,
    "linear": LinearConfig,
    "shortcut": ShortcutConfig,
    "csv": CSVConfig,
}


class TestConnectionRequest(BaseModel):
    platform: str
    config: Dict[str, Any]

    @field_validator("config")
    @classmethod
    def validate_config_for_platform(cls, config: dict, info) -> dict:
        platform = info.data.get("platform")
        model_cls = _CONFIG_MODELS.get(platform)
        if model_cls:
            # Parse via the platform model to enforce required fields
            model_cls(**{"platform": platform, **config})
        return config


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    projects_found: List[Dict[str, Any]] = []

class DiscoverStatusesRequest(BaseModel):
    platform: str
    config: Dict[str, Any]
    board_id: str

class DiscoverStatusesResponse(BaseModel):
    statuses: List[str]

@router.post("/test", response_model=TestConnectionResponse)
def test_connection(data: TestConnectionRequest):
    try:
        connector = get_connector(data.platform, data.config, [])
        result = connector.test_connection()
        return TestConnectionResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            projects_found=result.get("boards", result.get("projects", []))
        )
    except Exception as e:
        return TestConnectionResponse(success=False, message=str(e))

@router.post("/discover-statuses", response_model=DiscoverStatusesResponse)
def discover_statuses(data: DiscoverStatusesRequest):
    try:
        connector = get_connector(data.platform, data.config, [])
        statuses = connector.discover_statuses(data.board_id)
        return DiscoverStatusesResponse(statuses=statuses)
    except Exception as e:
        return DiscoverStatusesResponse(statuses=[])
