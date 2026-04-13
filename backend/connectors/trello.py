import pandas as pd
import logging
import requests
from datetime import datetime
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class TrelloConnector(BaseConnector):
    BASE_URL = "https://api.trello.com/1"
    
    def __init__(self, config: dict, workflow_steps: list):
        super().__init__(config, workflow_steps)
        self.api_key = config.get("api_key", "")
        self.token = config.get("token", "")
    
    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}/{path}"
        p = {"key": self.api_key, "token": self.token}
        if params:
            p.update(params)
        r = requests.get(url, params=p, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def test_connection(self) -> dict:
        try:
            boards = self._get("members/me/boards", {"filter": "open"})
            return {
                "success": True,
                "message": f"Connected. Found {len(boards)} boards.",
                "boards": [{"id": b["id"], "name": b["name"]} for b in boards]
            }
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}
    
    def discover_statuses(self, board_id: str) -> list:
        try:
            lists = self._get(f"boards/{board_id}/lists", {"filter": "open"})
            return [l["name"] for l in lists]
        except Exception as e:
            logger.error(f"Error discovering Trello lists: {e}")
            return []
    
    def fetch_items(self) -> pd.DataFrame:
        board_id = self.config.get("board_id", "")
        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]
        
        lists = self._get(f"boards/{board_id}/lists", {"filter": "open"})
        list_map = {l["id"]: l["name"] for l in lists}
        
        cards = self._get(f"boards/{board_id}/cards", {
            "filter": "all",
            "fields": "id,name,idList,dateLastActivity,desc",
            "members": "true",
            "customFieldItems": "true"
        })
        
        records = []
        for card in cards:
            timestamps = {name: None for name in step_names}
            
            # Get card actions (move history)
            try:
                actions = self._get(f"cards/{card['id']}/actions", {
                    "filter": "updateCard",
                    "fields": "date,data"
                })
                for action in sorted(actions, key=lambda a: a["date"]):
                    data = action.get("data", {})
                    if "listAfter" in data:
                        list_name = data["listAfter"].get("name", "").lower()
                        step_name = status_map.get(list_name)
                        if step_name and timestamps[step_name] is None:
                            timestamps[step_name] = pd.to_datetime(action["date"])
            except Exception:
                pass
            
            record = {
                "item_key": card["id"][:8],
                "item_type": "Card",
                "creator": None,
                "created_at": pd.to_datetime(card.get("dateLastActivity")),
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
            
            first_step = self.workflow_steps[0]["display_name"] if self.workflow_steps else None
            if first_step and done_steps:
                done_col = done_steps[-1]["display_name"]
                first_ts = timestamps.get(first_step) or record["created_at"]
                if first_ts and timestamps.get(done_col):
                    record["lead_time_days"] = (timestamps[done_col] - first_ts).days
                else:
                    record["lead_time_days"] = None
            
            records.append(record)
        
        return pd.DataFrame(records)
