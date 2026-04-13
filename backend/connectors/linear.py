import pandas as pd
import httpx
import logging
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class LinearConnector(BaseConnector):
    API_URL = "https://api.linear.app/graphql"
    
    def test_connection(self) -> dict:
        try:
            api_key = self.config.get("api_key", "")
            query = """{ teams { nodes { id name } } }"""
            resp = httpx.post(
                self.API_URL,
                json={"query": query},
                headers={"Authorization": api_key},
                timeout=10
            )
            data = resp.json()
            teams = data.get("data", {}).get("teams", {}).get("nodes", [])
            return {
                "success": True,
                "message": f"Connected. Found {len(teams)} teams.",
                "boards": [{"id": t["id"], "name": t["name"]} for t in teams]
            }
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}
    
    def discover_statuses(self, board_id: str) -> list:
        try:
            api_key = self.config.get("api_key", "")
            query = f"""{{ workflowStates(filter: {{ team: {{ id: {{ eq: "{board_id}" }} }} }}) {{ nodes {{ id name }} }} }}"""
            resp = httpx.post(
                self.API_URL,
                json={"query": query},
                headers={"Authorization": api_key},
                timeout=10
            )
            data = resp.json()
            states = data.get("data", {}).get("workflowStates", {}).get("nodes", [])
            return [s["name"] for s in states]
        except Exception as e:
            logger.error(f"Error discovering Linear states: {e}")
            return []
    
    def fetch_items(self) -> pd.DataFrame:
        api_key = self.config.get("api_key", "")
        team_id = self.config.get("team_id", "")
        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]
        
        query = """
        query Issues($teamId: String!) {
          issues(filter: { team: { id: { eq: $teamId } } }, first: 200) {
            nodes {
              id identifier title state { name } creator { name }
              createdAt completedAt
              history { nodes { createdAt toState { name } } }
            }
          }
        }
        """
        resp = httpx.post(
            self.API_URL,
            json={"query": query, "variables": {"teamId": team_id}},
            headers={"Authorization": api_key},
            timeout=30
        )
        data = resp.json()
        issues = data.get("data", {}).get("issues", {}).get("nodes", [])
        
        records = []
        for issue in issues:
            timestamps = {name: None for name in step_names}
            
            for history in sorted(issue.get("history", {}).get("nodes", []), key=lambda h: h["createdAt"]):
                if history.get("toState"):
                    state_name = history["toState"]["name"].lower()
                    step_name = status_map.get(state_name)
                    if step_name and timestamps[step_name] is None:
                        timestamps[step_name] = pd.to_datetime(history["createdAt"])
            
            record = {
                "item_key": issue.get("identifier", issue["id"][:8]),
                "item_type": "Issue",
                "creator": issue.get("creator", {}).get("name") if issue.get("creator") else None,
                "created_at": pd.to_datetime(issue["createdAt"]),
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
