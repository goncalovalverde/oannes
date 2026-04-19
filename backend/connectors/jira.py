import pandas as pd
import logging
import requests
from datetime import datetime
from connectors.base import BaseConnector
from jira import JIRAError

logger = logging.getLogger(__name__)

# Enable debug logging for requests library to see HTTP headers/responses
logging.getLogger("urllib3").setLevel(logging.DEBUG)


def _format_jira_error(error: Exception, context: str = "") -> str:
    """Format Jira errors into user-friendly messages.
    
    Args:
        error: The exception that occurred
        context: Additional context about what operation failed
        
    Returns:
        A human-readable error message suitable for display to users
    """
    error_str = str(error)
    
    logger.debug(f"Formatting error: {type(error).__name__}: {error_str}")
    
    if isinstance(error, JIRAError):
        status = getattr(error, 'status_code', None)
        logger.debug(f"JIRAError with status {status}")
        
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

    # Handle Jira application-level error messages in 200 responses (e.g. deprecated APIs)
    if 'api has been removed' in error_str.lower() or 'migrate to' in error_str.lower():
        return (
            "Jira rejected the request: the API endpoint used by Oannes has been removed. "
            "This is a known Jira Cloud change (CHANGE-2046). Please ensure you are running "
            "the latest version of Oannes."
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

    def _get_auth_headers(self) -> dict:
        """Return auth headers based on auth type (PAT or API token)."""
        auth_type = self.config.get("auth_type", "api_token")
        logger.debug(f"[Jira Auth] Using auth_type: {auth_type}")
        
        if auth_type == "personal_access_token":
            # PAT uses Bearer token
            pat = self.config.get('personal_access_token', '')
            logger.debug(f"[Jira Auth] PAT mode - token length: {len(pat)}")
            return {"Authorization": f"Bearer {pat}"}
        # Default: API token uses basic auth
        logger.debug("[Jira Auth] API token mode (Basic Auth)")
        return {}

    def _get_client(self):
        if self._jira is None:
            from jira import JIRA
            
            auth_type = self.config.get("auth_type", "api_token")
            logger.debug(f"[Jira Client] Initializing with auth_type: {auth_type}")
            
            if auth_type == "personal_access_token":
                # For PAT, we can't use the jira library's basic_auth
                # Just create a dummy JIRA client; we'll use requests for actual calls
                # The jira library still expects some form of auth for initialization
                logger.debug(f"[Jira Client] Creating JIRA client for PAT (will use requests directly)")
                self._jira = JIRA(
                    server=self.config["url"],
                    options={"agile_rest_path": "agile"}
                )
            else:
                # API token auth
                email = self.config.get("email", "")
                token = self.config.get("api_token", "")
                logger.debug(f"[Jira Client] Creating JIRA client with API token (email: {email}, token length: {len(token)})")
                self._jira = JIRA(
                    server=self.config["url"],
                    basic_auth=(email, token)
                )
        return self._jira

    def _search_issues_v3(self, jql: str, start: int, batch: int) -> dict:
        """Call Jira Cloud REST API v3 /search/jql directly.

        Jira Cloud removed /rest/api/2/search (CHANGE-2046).
        The jira library still uses v2; we call v3 ourselves.
        """
        url = f"{self.config['url'].rstrip('/')}/rest/api/3/search/jql"
        params = {
            "jql": jql,
            "startAt": start,
            "maxResults": batch,
            "expand": "changelog",
            "fields": "*all",
        }
        
        # Prepare auth based on auth type
        headers = {}
        auth = None
        
        auth_type = self.config.get("auth_type", "api_token")
        logger.debug(f"[Jira Search] URL: {url}")
        logger.debug(f"[Jira Search] Auth type: {auth_type}")
        
        if auth_type == "personal_access_token":
            # PAT uses Bearer token
            pat = self.config.get("personal_access_token", "")
            logger.debug(f"[Jira Search] Using Bearer token (length: {len(pat)})")
            headers = {"Authorization": f"Bearer {pat}"}
        else:
            # API token uses basic auth
            email = self.config.get("email", "")
            logger.debug(f"[Jira Search] Using basic auth with email: {email}")
            auth = (email, self.config.get("api_token", ""))
        
        logger.debug(f"[Jira Search] Making request to {url}...")
        try:
            resp = requests.get(
                url,
                params=params,
                auth=auth,
                headers=headers if headers else None,
                timeout=30,
                allow_redirects=True,
            )
            logger.debug(f"[Jira Search] Response status: {resp.status_code}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[Jira Search] Request failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

        # Surface any Jira application-level errors embedded in a 200 response
        if "errorMessages" in data and data["errorMessages"]:
            raise JIRAError(status_code=400, text="; ".join(data["errorMessages"]))

        return data

    def test_connection(self) -> dict:
        logger.info(f"[Jira Test] Starting connection test with auth_type: {self.config.get('auth_type')}")
        logger.debug(f"[Jira Test] URL: {self.config.get('url')}")
        try:
            auth_type = self.config.get("auth_type", "api_token")
            
            if auth_type == "personal_access_token":
                # For PAT, try Bearer token with allow_redirects
                logger.debug("[Jira Test] Using PAT token with Bearer authorization")
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/myself"
                pat = self.config.get('personal_access_token', '')
                
                # Try Bearer token - allow redirects
                headers = {"Authorization": f"Bearer {pat}"}
                logger.debug("[Jira Test] Sending request with Bearer token (allowing redirects)")
                resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                logger.debug(f"[Jira Test] Response status: {resp.status_code}")
                logger.debug(f"[Jira Test] Response headers: {dict(resp.headers)}")
                
                if resp.status_code not in [200, 401]:
                    logger.debug(f"[Jira Test] Response text (first 500 chars): {resp.text[:500]}")
                
                resp.raise_for_status()
                user = resp.json()
                logger.info(f"[Jira Test] ✅ Authenticated as: {user.get('displayName', 'Unknown')}")
                
                # Now fetch projects with same auth method
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/projects"
                resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                resp.raise_for_status()
                data = resp.json()
                projects = data.get('values', [])
                
                return {
                    "success": True,
                    "message": f"Connected successfully. Found {len(projects)} projects.",
                    "boards": [{"id": p.get("key"), "name": p.get("name")} for p in projects]
                }
            else:
                # API token auth - use jira library
                logger.debug("[Jira Test] Using JIRA library for API token")
                jira = self._get_client()
                projects = jira.projects()
                logger.info(f"[Jira Test] ✅ Connected successfully. Found {len(projects)} projects")
                return {
                    "success": True,
                    "message": f"Connected successfully. Found {len(projects)} projects.",
                    "boards": [{"id": p.key, "name": p.name} for p in projects]
                }
        except Exception as e:
            user_message = _format_jira_error(e, context="during connection test")
            logger.error(f"[Jira Test] ❌ Connection failed: {type(e).__name__}: {str(e)}", exc_info=True)
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
        project_key = self.config.get("project_key", "")
        jql = self.config.get("jql", f"project = {project_key} ORDER BY created ASC")

        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]

        all_issues = []
        start = 0
        batch = 100

        while True:
            data = self._search_issues_v3(jql, start, batch)
            issues = data.get("issues", [])
            if not issues:
                break
            all_issues.extend(issues)
            if len(issues) < batch:
                break
            start += batch

        records = []
        for issue in all_issues:
            fields = issue.get("fields", {})
            changelog = issue.get("changelog", {})
            timestamps = {name: None for name in step_names}

            for history in changelog.get("histories", []):
                created = pd.to_datetime(history["created"])
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        to_status = (item.get("toString") or "").lower()
                        step_name = status_map.get(to_status)
                        if step_name and timestamps.get(step_name) is None:
                            timestamps[step_name] = created

            record = {
                "item_key": issue["key"],
                "item_type": (fields.get("issuetype") or {}).get("name"),
                "creator": ((fields.get("creator") or {}).get("displayName")),
                "created_at": pd.to_datetime(fields.get("created")),
                "workflow_timestamps": {
                    k: v.isoformat() if v else None for k, v in timestamps.items()
                },
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
