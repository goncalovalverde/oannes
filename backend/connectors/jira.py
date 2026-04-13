import pandas as pd
import logging
from datetime import datetime
from connectors.base import BaseConnector
from jira import JIRAError

logger = logging.getLogger(__name__)


def _format_jira_error(error: Exception, context: str = "") -> str:
    """Format Jira errors into user-friendly messages.
    
    Args:
        error: The exception that occurred
        context: Additional context about what operation failed
        
    Returns:
        A human-readable error message suitable for display to users
    """
    error_str = str(error)
    
    if isinstance(error, JIRAError):
        status = getattr(error, 'status_code', None)
        
        if status == 401:
            return (
                "Invalid Jira credentials. Please check your email/username and API token. "
                "API tokens can be generated at: https://id.atlassian.com/manage-profile/security/api-tokens"
            )
        elif status == 403:
            return (
                "You don't have permission to access this Jira project. "
                "Your Jira user may not have 'Browse Projects' permission. "
                "Ask your Jira administrator for access."
            )
        elif status == 404:
            return (
                f"Jira project or resource not found. {context} "
                "Please check the project key and try again."
            )
        elif status == 400:
            return (
                f"Invalid Jira request. {context} "
                "Check your project key and configuration."
            )
        elif status == 500:
            return (
                "Jira server error (500). The Jira instance may be down or misconfigured. "
                "Please try again in a few moments."
            )
        else:
            return (
                f"Jira API error ({status}). {context} "
                "Check your Jira URL and try again."
            )
    
    # Handle JSON parsing errors
    if 'json' in error_str.lower() or 'expecting value' in error_str.lower():
        return (
            "Jira API returned invalid data. This usually means: (1) your Jira URL is wrong, "
            "(2) the server is misconfigured, or (3) there's a proxy/firewall interfering. "
            "Check your Jira URL and network connection."
        )
    
    # Handle connection errors
    if 'timeout' in error_str.lower() or 'connection' in error_str.lower():
        return (
            "Cannot connect to Jira server. Check that the Jira URL is correct "
            "and your network connection is active. (Connection timeout)"
        )
    
    if 'ssl' in error_str.lower() or 'certificate' in error_str.lower():
        return (
            "SSL certificate error connecting to Jira. "
            "Your company's firewall or proxy may be interfering. "
            "Try removing 'https://' verification or contact your IT team."
        )
    
    # Fallback for unknown errors
    return f"Jira connection error: {error_str[:100]}"

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
            user_message = _format_jira_error(e, context="during connection test")
            logger.error(f"Jira connection error: {e}", exc_info=True)
            return {"success": False, "message": user_message, "boards": []}
    
    def discover_statuses(self, board_id: str) -> list:
        try:
            jira = self._get_client()
            statuses = jira.statuses()
            return list(set(s.name for s in statuses))
        except Exception as e:
            user_message = _format_jira_error(e, context=f"discovering statuses for project {board_id}")
            logger.error(f"Error discovering Jira statuses: {e}", exc_info=True)
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
