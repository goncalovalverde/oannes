import pandas as pd
import logging
from datetime import datetime
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class JiraConnector(BaseConnector):
    def __init__(self, config: dict, workflow_steps: list):
        super().__init__(config, workflow_steps)
        self._jira = None
    
    def _get_client(self):
        if self._jira is None:
            from jira import JIRA
            self._jira = JIRA(
                server=self.config["url"],
                basic_auth=(self.config["email"], self.config["api_token"])
            )
        return self._jira
    
    def test_connection(self) -> dict:
        try:
            jira = self._get_client()
            projects = jira.projects()
            return {
                "success": True,
                "message": f"Connected successfully. Found {len(projects)} projects.",
                "boards": [{"id": p.key, "name": p.name} for p in projects]
            }
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}
    
    def discover_statuses(self, board_id: str) -> list:
        try:
            jira = self._get_client()
            statuses = jira.statuses()
            return list(set(s.name for s in statuses))
        except Exception as e:
            logger.error(f"Error discovering Jira statuses: {e}")
            return []
    
    def fetch_items(self) -> pd.DataFrame:
        jira = self._get_client()
        project_key = self.config.get("project_key", "")
        jql = self.config.get("jql", f"project = {project_key} ORDER BY created ASC")
        
        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]
        
        all_issues = []
        start = 0
        batch = 100
        
        while True:
            issues = jira.search_issues(jql, startAt=start, maxResults=batch, expand="changelog")
            if not issues:
                break
            all_issues.extend(issues)
            if len(issues) < batch:
                break
            start += batch
        
        records = []
        for issue in all_issues:
            timestamps = {name: None for name in step_names}
            
            # Process changelog to get first entry into each status
            for history in issue.changelog.histories:
                created = pd.to_datetime(history.created)
                for item in history.items:
                    if item.field == "status":
                        to_status = item.toString.lower()
                        step_name = status_map.get(to_status)
                        if step_name and timestamps[step_name] is None:
                            timestamps[step_name] = created
            
            record = {
                "item_key": issue.key,
                "item_type": issue.fields.issuetype.name,
                "creator": getattr(issue.fields.creator, "displayName", None),
                "created_at": pd.to_datetime(issue.fields.created),
                "workflow_timestamps": {k: v.isoformat() if v else None for k, v in timestamps.items()},
            }
            
            # Calculate cycle/lead time
            start_steps = [s for s in self.workflow_steps if s["stage"] == "start"]
            done_steps = [s for s in self.workflow_steps if s["stage"] == "done"]
            
            if start_steps and done_steps:
                start_col = start_steps[0]["display_name"]
                done_col = done_steps[-1]["display_name"]
                if timestamps.get(start_col) and timestamps.get(done_col):
                    record["cycle_time_days"] = (timestamps[done_col] - timestamps[start_col]).days
                else:
                    record["cycle_time_days"] = None
            
            first_step = self.workflow_steps[0]["display_name"] if self.workflow_steps else None
            if first_step and done_steps:
                done_col = done_steps[-1]["display_name"]
                first_ts = timestamps.get(first_step) or record["created_at"]
                if first_ts and timestamps.get(done_col):
                    record["lead_time_days"] = (timestamps[done_col] - first_ts).days
                else:
                    record["lead_time_days"] = None
            
            records.append(record)
        
        df = pd.DataFrame(records)
        return df
