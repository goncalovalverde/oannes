from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel, field_validator
from typing import List, Any, Optional, Dict
from connectors import get_connector
from models.connector_config import validate_connector_config

router = APIRouter()


class TestConnectionRequest(BaseModel):
    platform: str
    config: Dict[str, Any]

    @field_validator("config")
    @classmethod
    def validate_config_for_platform(cls, config: dict, info) -> dict:
        import logging
        logger = logging.getLogger(__name__)
        platform = info.data.get("platform")
        if platform:
            try:
                validate_connector_config(platform, config)
            except ValueError as e:
                raise ValueError(str(e))
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

