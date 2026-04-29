import pandas as pd
import logging
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class GitLabConnector(BaseConnector):
    def _get_client(self):
        import gitlab
        url = self.config.get("url", "https://gitlab.com")
        token = self.config.get("access_token", "")
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()
        return gl
    
    def test_connection(self) -> dict:
        try:
            gl = self._get_client()
            projects = gl.projects.list(membership=True, per_page=20)
            return {
                "success": True,
                "message": f"Connected. Found {len(projects)} projects.",
                "boards": [{"id": str(p.id), "name": p.name_with_namespace} for p in projects]
            }
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}
    
    def discover_statuses(self, board_id: str) -> list:
        try:
            gl = self._get_client()
            project = gl.projects.get(board_id)
            labels = project.labels.list(all=True)
            return [l.name for l in labels]
        except Exception as e:
            logger.error(f"Error discovering GitLab labels: {e}")
            return []
    
    def fetch_items(self) -> pd.DataFrame:
        gl = self._get_client()
        project_key = self.config.get("project_key", "")
        
        if not project_key:
            raise ValueError("project_key required for GitLab connector")
        
        project = gl.projects.get(project_key)
        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]
        
        issues = project.issues.list(all=True, order_by="created_at", sort="asc")
        
        records = []
        for issue in issues:
            timestamps = {name: None for name in step_names}
            
            try:
                label_events = issue.resourcelabelevents.list(all=True)
                for event in sorted(label_events, key=lambda e: e.created_at):
                    if event.action == "add":
                        label_name = event.label.get("name", "").lower() if event.label else ""
                        step_name = status_map.get(label_name)
                        if step_name and timestamps[step_name] is None:
                            timestamps[step_name] = pd.to_datetime(event.created_at)
            except Exception:
                pass
            
            done_steps = [s for s in self.workflow_steps if s["stage"] == "done"]
            if done_steps and issue.state == "closed" and issue.closed_at:
                done_col = done_steps[-1]["display_name"]
                if timestamps[done_col] is None:
                    timestamps[done_col] = pd.to_datetime(issue.closed_at)
            
            record = {
                "item_key": f"#{issue.iid}",
                "item_type": "Issue",
                "creator": issue.author.get("name") if issue.author else None,
                "created_at": pd.to_datetime(issue.created_at),
                "workflow_timestamps": {k: v.isoformat() if v else None for k, v in timestamps.items()},
                "status_transitions": [],
            }
            
            start_steps = [s for s in self.workflow_steps if s["stage"] == "start"]
            if start_steps and done_steps:
                start_col = start_steps[0]["display_name"]
                done_col = done_steps[-1]["display_name"]
                if timestamps.get(start_col) and timestamps.get(done_col):
                    record["cycle_time_days"] = (timestamps[done_col] - timestamps[start_col]).days
                else:
                    record["cycle_time_days"] = None
            
            if self.workflow_steps and done_steps:
                done_col = done_steps[-1]["display_name"]
                first_ts = record["created_at"]
                if first_ts and timestamps.get(done_col):
                    record["lead_time_days"] = (timestamps[done_col] - first_ts).days
                else:
                    record["lead_time_days"] = None
            
            records.append(record)
        
        return pd.DataFrame(records)
