import pandas as pd
import logging
import os
import io
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

REQUIRED_COLS = {"item_key", "item_type", "created_at"}


def _read_df(source, filename: str = "") -> pd.DataFrame:
    """Read a CSV or Excel file from a file path or BytesIO buffer."""
    name = (filename or "").lower()
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(source)
    return pd.read_csv(source)


def _read_df_preview(source, filename: str = "", nrows: int = 1) -> pd.DataFrame:
    name = (filename or "").lower()
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(source, nrows=nrows)
    return pd.read_csv(source, nrows=nrows)


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

    @staticmethod
    def validate_bytes(content: bytes, filename: str) -> dict:
        """Validate a CSV/Excel file from bytes. Returns {success, message, columns, boards}."""
        try:
            df = _read_df_preview(content, filename, nrows=1)
            columns = list(df.columns)
            missing = REQUIRED_COLS - set(columns)
            if missing:
                return {
                    "success": False,
                    "message": f"Missing required columns: {sorted(missing)}",
                    "columns": columns,
                    "boards": [],
                }
            return {
                "success": True,
                "message": f"File valid. Found {len(columns)} columns.",
                "columns": columns,
                "boards": [{"id": "csv", "name": filename}],
            }
        except Exception as e:
            return {"success": False, "message": str(e), "columns": [], "boards": []}

    def discover_statuses(self, board_id: str) -> list:
        path = self.config.get("file_path", "")
        try:
            df = pd.read_csv(path, nrows=0)
            standard = {"item_key", "item_type", "creator", "created_at", "cycle_time_days", "lead_time_days"}
            return [c for c in df.columns if c not in standard]
        except Exception:
            return []

    @staticmethod
    def discover_columns_from_bytes(content: bytes, filename: str) -> list:
        """Return non-standard columns from an in-memory file (for workflow mapping)."""
        try:
            df = _read_df_preview(content, filename, nrows=0)
            standard = {"item_key", "item_type", "creator", "created_at", "cycle_time_days", "lead_time_days"}
            return [c for c in df.columns if c not in standard]
        except Exception:
            return []

    def fetch_items(self) -> pd.DataFrame:
        """CSV projects do not use the standard fetch_items flow.
        
        They use the /sync/{project_id}/csv-upload endpoint for file upload.
        This method is provided for interface completeness but is not called in normal operation.
        """
        raise NotImplementedError(
            "CSV projects require file upload via POST /sync/{project_id}/csv-upload. "
            "Use fetch_from_bytes() instead."
        )

    def fetch_from_bytes(self, content: bytes, filename: str) -> pd.DataFrame:
        """Process an in-memory CSV/Excel file and return a records DataFrame."""
        df = _read_df(content, filename)
        return self._build_records(df)

    def _build_records(self, df: pd.DataFrame) -> pd.DataFrame:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        records = []
        for _, row in df.iterrows():
            timestamps = {}
            for step in self.workflow_steps:
                name = step["display_name"]
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
                "status_transitions": [],
            }

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

