import pandas as pd
import logging
import os
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

REQUIRED_COLS = {"item_key", "item_type", "created_at"}


class CSVConnector(BaseConnector):

    def test_connection(self) -> dict:
        path = self.config.get("file_path", "")
        if not path or not os.path.exists(path):
            return {"success": False, "message": f"File not found: {path}", "boards": []}
        try:
            df = pd.read_csv(path, nrows=1)
            missing = REQUIRED_COLS - set(df.columns)
            if missing:
                return {"success": False, "message": f"Missing required columns: {missing}", "boards": []}
            return {"success": True, "message": f"CSV is valid. Columns: {list(df.columns)}", "boards": [{"id": "csv", "name": os.path.basename(path)}]}
        except Exception as e:
            return {"success": False, "message": str(e), "boards": []}

    def discover_statuses(self, board_id: str) -> list:
        path = self.config.get("file_path", "")
        try:
            df = pd.read_csv(path, nrows=0)
            # Return columns that look like workflow steps (exclude standard ones)
            standard = {"item_key", "item_type", "creator", "created_at", "cycle_time_days", "lead_time_days"}
            return [c for c in df.columns if c not in standard]
        except Exception:
            return []

    def fetch_items(self) -> pd.DataFrame:
        path = self.config.get("file_path", "")
        df = pd.read_csv(path)

        step_names = [s["display_name"] for s in self.workflow_steps]

        # Ensure created_at is datetime
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        records = []
        for _, row in df.iterrows():
            timestamps = {}
            for step in self.workflow_steps:
                name = step["display_name"]
                # Try to find matching column in CSV
                for src_status in step.get("source_statuses", [name]):
                    if src_status in df.columns:
                        val = row.get(src_status)
                        if pd.notna(val):
                            timestamps[name] = pd.to_datetime(val, errors="coerce")
                            break
                if name not in timestamps:
                    timestamps[name] = None

            record = {
                "item_key": str(row.get("item_key", "")),
                "item_type": str(row.get("item_type", "Task")),
                "creator": row.get("creator"),
                "created_at": row["created_at"],
                "workflow_timestamps": {k: v.isoformat() if v else None for k, v in timestamps.items()},
            }

            # Use provided cycle/lead time or calculate
            if "cycle_time_days" in df.columns and pd.notna(row.get("cycle_time_days")):
                record["cycle_time_days"] = float(row["cycle_time_days"])
            else:
                record.update(self._calc_times(timestamps))

            if "lead_time_days" in df.columns and pd.notna(row.get("lead_time_days")):
                record["lead_time_days"] = float(row["lead_time_days"])

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
