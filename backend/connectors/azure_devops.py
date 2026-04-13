import pandas as pd
import logging
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class AzureDevOpsConnector(BaseConnector):

    def test_connection(self) -> dict:
        try:
            from azure.devops.connection import Connection
            from msrest.authentication import BasicAuthentication
            creds = BasicAuthentication("", self.config["personal_access_token"])
            conn = Connection(base_url=self.config["org_url"], creds=creds)
            core_client = conn.clients.get_core_client()
            projects = core_client.get_projects()
            items = list(projects)
            return {
                "success": True,
                "message": f"Connected. Found {len(items)} projects.",
                "boards": [{"id": p.id, "name": p.name} for p in items],
            }
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}

    def discover_statuses(self, board_id: str) -> list:
        try:
            from azure.devops.connection import Connection
            from msrest.authentication import BasicAuthentication
            creds = BasicAuthentication("", self.config["personal_access_token"])
            conn = Connection(base_url=self.config["org_url"], creds=creds)
            wit_client = conn.clients.get_work_item_tracking_client()
            states = wit_client.get_work_item_type_states(board_id, "Task")
            return [s.name for s in states]
        except Exception as e:
            logger.error(f"Azure DevOps discover_statuses error: {e}")
            return []

    def fetch_items(self) -> pd.DataFrame:
        from azure.devops.connection import Connection
        from msrest.authentication import BasicAuthentication
        from azure.devops.v7_1.work_item_tracking.models import Wiql

        creds = BasicAuthentication("", self.config["personal_access_token"])
        conn = Connection(base_url=self.config["org_url"], creds=creds)
        wit_client = conn.clients.get_work_item_tracking_client()

        project = self.config.get("project_key", "")
        wiql = Wiql(query=f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project}' ORDER BY [System.CreatedDate]")
        result = wit_client.query_by_wiql(wiql)
        if not result.work_items:
            return pd.DataFrame()

        ids = [wi.id for wi in result.work_items[:500]]
        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]

        records = []
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            items = wit_client.get_work_items(batch, expand="All")
            for item in items:
                fields = item.fields
                timestamps = {name: None for name in step_names}

                # Get history via revisions
                try:
                    revisions = wit_client.get_revisions(item.id)
                    for rev in revisions:
                        state = rev.fields.get("System.State", "")
                        changed = pd.to_datetime(rev.fields.get("System.ChangedDate"))
                        step_name = status_map.get(state.lower())
                        if step_name and timestamps[step_name] is None:
                            timestamps[step_name] = changed
                except Exception:
                    pass

                record = {
                    "item_key": str(item.id),
                    "item_type": fields.get("System.WorkItemType", "Unknown"),
                    "creator": fields.get("System.CreatedBy", {}).get("displayName") if isinstance(fields.get("System.CreatedBy"), dict) else str(fields.get("System.CreatedBy", "")),
                    "created_at": pd.to_datetime(fields.get("System.CreatedDate")),
                    "workflow_timestamps": {k: v.isoformat() if v else None for k, v in timestamps.items()},
                }
                record.update(self._calc_times(timestamps))
                records.append(record)

        return pd.DataFrame(records) if records else pd.DataFrame()

    def _calc_times(self, timestamps: dict) -> dict:
        start_steps = [s for s in self.workflow_steps if s["stage"] == "start"]
        done_steps = [s for s in self.workflow_steps if s["stage"] == "done"]
        result = {"cycle_time_days": None, "lead_time_days": None}
        if start_steps and done_steps:
            s = timestamps.get(start_steps[0]["display_name"])
            d = timestamps.get(done_steps[-1]["display_name"])
            if s and d:
                result["cycle_time_days"] = (d - s).days
        if self.workflow_steps and done_steps:
            f = timestamps.get(self.workflow_steps[0]["display_name"])
            d = timestamps.get(done_steps[-1]["display_name"])
            if f and d:
                result["lead_time_days"] = (d - f).days
        return result
