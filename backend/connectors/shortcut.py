import pandas as pd
import httpx
import logging
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class ShortcutConnector(BaseConnector):
    BASE_URL = "https://api.app.shortcut.com/api/v3"
    
    def _headers(self):
        return {"Shortcut-Token": self.config.get("api_token", "")}
    
    def test_connection(self) -> dict:
        try:
            resp = httpx.get(f"{self.BASE_URL}/member", headers=self._headers(), timeout=10)
            resp.raise_for_status()
            projects_resp = httpx.get(f"{self.BASE_URL}/projects", headers=self._headers(), timeout=10)
            projects = projects_resp.json() if projects_resp.status_code == 200 else []
            return {
                "success": True,
                "message": f"Connected. Found {len(projects)} projects.",
                "boards": [{"id": str(p["id"]), "name": p["name"]} for p in projects]
            }
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}
    
    def discover_statuses(self, board_id: str) -> list:
        try:
            resp = httpx.get(f"{self.BASE_URL}/workflows", headers=self._headers(), timeout=10)
            workflows = resp.json()
            statuses = []
            for wf in workflows:
                for state in wf.get("states", []):
                    statuses.append(state["name"])
            return list(set(statuses))
        except Exception as e:
            logger.error(f"Error discovering Shortcut statuses: {e}")
            return []
    
    def fetch_items(self) -> pd.DataFrame:
        project_id = self.config.get("project_id", "")
        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]
        
        wf_resp = httpx.get(f"{self.BASE_URL}/workflows", headers=self._headers(), timeout=10)
        workflow_states = {}
        for wf in wf_resp.json():
            for state in wf.get("states", []):
                workflow_states[state["id"]] = state["name"]
        
        search_resp = httpx.post(
            f"{self.BASE_URL}/stories/search",
            headers=self._headers(),
            json={"project_ids": [int(project_id)]} if project_id else {},
            timeout=30
        )
        stories = search_resp.json() if search_resp.status_code == 200 else []
        
        records = []
        for story in stories:
            timestamps = {name: None for name in step_names}
            
            try:
                history_resp = httpx.get(
                    f"{self.BASE_URL}/stories/{story['id']}/history",
                    headers=self._headers(),
                    timeout=10
                )
                if history_resp.status_code == 200:
                    for event in sorted(history_resp.json(), key=lambda e: e.get("changed_at", "")):
                        for change in event.get("changes", {}).get("workflow_state_id", {}).get("new", []):
                            state_name = workflow_states.get(change, "").lower()
                            step_name = status_map.get(state_name)
                            if step_name and timestamps[step_name] is None:
                                timestamps[step_name] = pd.to_datetime(event.get("changed_at"))
            except Exception:
                pass
            
            record = {
                "item_key": f"sc-{story['id']}",
                "item_type": story.get("story_type", "story").title(),
                "creator": None,
                "created_at": pd.to_datetime(story.get("created_at")),
                "workflow_timestamps": {k: v.isoformat() if v else None for k, v in timestamps.items()},
            }
            
            start_steps = [s for s in self.workflow_steps if s["stage"] == "start"]
            done_steps = [s for s in self.workflow_steps if s["stage"] == "done"]
            
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
