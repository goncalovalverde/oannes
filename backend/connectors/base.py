from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
import pandas as pd

class BaseConnector(ABC):
    def __init__(self, project_config: dict, workflow_steps: list, since: Optional[datetime] = None):
        self.config = project_config
        self.workflow_steps = workflow_steps
        self.since = since  # Fetch items created/updated after this timestamp
    
    def _build_status_map(self) -> dict:
        """Map source status names to workflow step display names."""
        mapping = {}
        for step in self.workflow_steps:
            for status in step.get("source_statuses", []):
                mapping[status.lower()] = step["display_name"]
        return mapping
    
    @abstractmethod
    def test_connection(self) -> dict:
        pass
    
    @abstractmethod
    def discover_statuses(self, board_id: str) -> List[str]:
        pass
    
    @abstractmethod
    def fetch_items(self) -> pd.DataFrame:
        pass
