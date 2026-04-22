from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Any, Optional, Dict, Literal, Union, Annotated
from connectors import get_connector

router = APIRouter()


# ---------------------------------------------------------------------------
# Per-platform config schemas
# ---------------------------------------------------------------------------

class JiraConfig(BaseModel):
    platform: Literal["jira"]
    url: str
    auth_type: Optional[str] = "api_token"
    email: Optional[str] = None
    api_token: Optional[str] = None
    personal_access_token: Optional[str] = None
    project_key: Optional[str] = None

    @model_validator(mode="after")
    def validate_auth_fields(self):
        auth_type = self.auth_type or "api_token"
        if auth_type == "api_token":
            if not self.email:
                raise ValueError("email is required for API token authentication")
            if not self.api_token:
                raise ValueError("api_token is required for API token authentication")
        elif auth_type == "personal_access_token":
            if not self.personal_access_token:
                raise ValueError("personal_access_token is required for Personal Access Token authentication")
        return self

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
    file_path: Optional[str] = None  # optional — uploads bypass file_path entirely

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
        import logging
        logger = logging.getLogger(__name__)
        platform = info.data.get("platform")
        logger.debug(f"[TestConnectionRequest Validator] Platform: {platform}")
        logger.debug(f"[TestConnectionRequest Validator] Config keys: {list(config.keys())}")
        logger.debug(f"[TestConnectionRequest Validator] Config: {config}")
        
        model_cls = _CONFIG_MODELS.get(platform)
        if model_cls:
            try:
                logger.debug(f"[TestConnectionRequest Validator] Validating with {model_cls.__name__}")
                validated = model_cls(**{"platform": platform, **config})
                logger.debug(f"[TestConnectionRequest Validator] ✅ Validation passed")
            except Exception as e:
                logger.error(f"[TestConnectionRequest Validator] ❌ Validation failed: {type(e).__name__}: {str(e)}")
                raise
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
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"[Test Connection] Received request: {data}")
    logger.debug(f"[Test Connection] Platform: {data.platform}")
    logger.debug(f"[Test Connection] Config: {data.config}")
    try:
        connector = get_connector(data.platform, data.config, [])
        result = connector.test_connection()
        return TestConnectionResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            projects_found=result.get("boards", result.get("projects", []))
        )
    except Exception as e:
        logger.error(f"[Test Connection] Error: {type(e).__name__}: {str(e)}", exc_info=True)
        return TestConnectionResponse(success=False, message=str(e))


@router.post("/discover-statuses", response_model=DiscoverStatusesResponse)
def discover_statuses(data: DiscoverStatusesRequest):
    try:
        connector = get_connector(data.platform, data.config, [])
        statuses = connector.discover_statuses(data.board_id)
        return DiscoverStatusesResponse(statuses=statuses)
    except Exception as e:
        return DiscoverStatusesResponse(statuses=[])


@router.post("/csv/upload-preview")
async def csv_upload_preview(file: UploadFile = File(...)):
    """Validate a CSV/Excel upload in memory. Returns {success, message, columns, boards}.

    Used by the wizard's 'Test Connection' step for CSV projects — no file is written to disk.
    """
    content = await file.read()
    filename = file.filename or "upload.csv"
    from connectors.csv_connector import CSVConnector
    result = CSVConnector.validate_bytes(content, filename)
    if result["success"]:
        result["extra_columns"] = CSVConnector.discover_columns_from_bytes(content, filename)
    return result

