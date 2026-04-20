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
                # For PAT, create JIRA client without auth, then set Bearer token in session
                logger.debug(f"[Jira Client] Creating JIRA client for PAT with Bearer token")
                
                # Create JIRA client without auth validation
                self._jira = JIRA(
                    server=self.config["url"],
                    options={"agile_rest_path": "agile"},
                    validate=False,  # Don't validate server on init
                    get_server_info=False  # Don't fetch server info on init
                )
                
                # Set Bearer token in the session
                pat = self.config.get("personal_access_token", "")
                if hasattr(self._jira, '_session'):
                    self._jira._session.headers.update({
                        'Authorization': f'Bearer {pat}'
                    })
                    logger.debug("[Jira Client] Set Bearer token in session headers")
                else:
                    logger.warning("[Jira Client] Could not find _session attribute")
            else:
                # API token auth
                email = self.config.get("email", "")
                token = self.config.get("api_token", "")
                logger.debug(f"[Jira Client] Creating JIRA client with API token (email: {email}, token length: {len(token)})")
                self._jira = JIRA(
                    server=self.config["url"],
                    basic_auth=(email, token),
                    validate=False,  # Skip server validation
                    get_server_info=False  # Don't fetch server info on init
                )
        return self._jira

    def _search_issues_v3(self, jql: str, start: int, batch: int) -> dict:
        """Call Jira Cloud REST API v3 /search/jql directly.

        Jira Cloud removed /rest/api/2/search (CHANGE-2046).
        The jira library still uses v2; we call v3 ourselves.
        
        Uses the jira client's ResilientSession to get automatic retry logic
        for rate limiting (429) and other transient errors.
        """
        url = f"{self.config['url'].rstrip('/')}/rest/api/3/search/jql"
        params = {
            "jql": jql,
            "startAt": start,
            "maxResults": batch,
            "expand": "changelog",
            "fields": "*all",
        }
        
        # Get the jira client (has ResilientSession with automatic retry logic)
        jira = self._get_client()
        
        # Log request details
        logger.debug(f"[Jira Search] >>> REQUEST")
        logger.debug(f"[Jira Search]     Method: GET")
        logger.debug(f"[Jira Search]     URL: {url}")
        logger.debug(f"[Jira Search]     Params: jql={jql[:100]}..." if len(jql) > 100 else f"[Jira Search]     Params: jql={jql}")
        logger.debug(f"[Jira Search]     Params: startAt={start}, maxResults={batch}")
        logger.debug(f"[Jira Search]     Headers: {dict(jira._session.headers)}")
        
        try:
            # Use jira._session (ResilientSession) for automatic retry logic
            # Note: ResilientSession handles timeout internally, don't override it
            resp = jira._session.get(url, params=params)
            
            # Log response details
            logger.debug(f"[Jira Search] <<< RESPONSE")
            logger.debug(f"[Jira Search]     Status Code: {resp.status_code}")
            logger.debug(f"[Jira Search]     Headers: {dict(resp.headers)}")
            logger.debug(f"[Jira Search]     Content-Length: {resp.headers.get('content-length', 'unknown')}")
            logger.debug(f"[Jira Search]     Content-Type: {resp.headers.get('content-type', 'unknown')}")
            
            resp.raise_for_status()
            data = resp.json()
            
            # Log response body summary
            logger.debug(f"[Jira Search]     Response Body: {len(str(data))} bytes")
            logger.debug(f"[Jira Search]     Issues Count: {len(data.get('issues', []))}")
            logger.debug(f"[Jira Search]     Total Issues: {data.get('total', 'unknown')}")
            
        except Exception as e:
            logger.error(f"[Jira Search] <<< ERROR RESPONSE")
            logger.error(f"[Jira Search]     Status: {getattr(e, 'status_code', 'unknown')}")
            logger.error(f"[Jira Search]     Type: {type(e).__name__}")
            logger.error(f"[Jira Search]     Message: {str(e)}")
            logger.error(f"[Jira Search] Request failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

        # Surface any Jira application-level errors embedded in a 200 response
        if "errorMessages" in data and data["errorMessages"]:
            logger.error(f"[Jira Search] Jira application error: {data['errorMessages']}")
            raise JIRAError(status_code=400, text="; ".join(data["errorMessages"]))

        return data

    def test_connection(self) -> dict:
        logger.info(f"[Jira Test] Starting connection test with auth_type: {self.config.get('auth_type')}")
        logger.debug(f"[Jira Test] URL: {self.config.get('url')}")
        try:
            auth_type = self.config.get("auth_type", "api_token")
            
            if auth_type == "personal_access_token":
                # For PAT, use Bearer token with jira client's ResilientSession for rate limit retry
                logger.debug("[Jira Test] Using PAT token with Bearer authorization")
                
                jira = self._get_client()
                
                # Test myself endpoint
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/myself"
                logger.debug(f"[Jira Test] >>> REQUEST (myself endpoint)")
                logger.debug(f"[Jira Test]     URL: {url}")
                logger.debug(f"[Jira Test]     Headers: {dict(jira._session.headers)}")
                
                resp = jira._session.get(url)
                
                logger.debug(f"[Jira Test] <<< RESPONSE")
                logger.debug(f"[Jira Test]     Status: {resp.status_code}")
                logger.debug(f"[Jira Test]     Content-Type: {resp.headers.get('content-type', 'unknown')}")
                
                if resp.status_code not in [200, 401]:
                    logger.debug(f"[Jira Test]     Response text (first 500 chars): {resp.text[:500]}")
                
                resp.raise_for_status()
                user = resp.json()
                logger.info(f"[Jira Test] ✅ Authenticated as: {user.get('displayName', 'Unknown')}")
                
                # Now fetch projects with same auth method
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/projects"
                logger.debug(f"[Jira Test] >>> REQUEST (projects endpoint)")
                logger.debug(f"[Jira Test]     URL: {url}")
                
                resp = jira._session.get(url)
                
                logger.debug(f"[Jira Test] <<< RESPONSE")
                logger.debug(f"[Jira Test]     Status: {resp.status_code}")
                logger.debug(f"[Jira Test]     Content-Length: {resp.headers.get('content-length', 'unknown')}")
                
                resp.raise_for_status()
                data = resp.json()
                projects = data.get('values', [])
                logger.debug(f"[Jira Test]     Projects Count: {len(projects)}")
                
                return {
                    "success": True,
                    "message": f"Connected successfully. Found {len(projects)} projects.",
                    "boards": [{"id": p.get("key"), "name": p.get("name")} for p in projects]
                }
            else:
                # API token auth - use jira library
                logger.debug("[Jira Test] Using JIRA library for API token")
                logger.debug(f"[Jira Test] >>> REQUEST (projects via jira library)")
                
                jira = self._get_client()
                projects = jira.projects()
                
                logger.debug(f"[Jira Test] <<< RESPONSE")
                logger.debug(f"[Jira Test]     Projects Count: {len(projects)}")
                logger.info(f"[Jira Test] ✅ Connected successfully. Found {len(projects)} projects")
                
                return {
                    "success": True,
                    "message": f"Connected successfully. Found {len(projects)} projects.",
                    "boards": [{"id": p.key, "name": p.name} for p in projects]
                }
        except Exception as e:
            logger.error(f"[Jira Test] <<< ERROR")
            logger.error(f"[Jira Test]     Exception Type: {type(e).__name__}")
            logger.error(f"[Jira Test]     Message: {str(e)}")
            if hasattr(e, 'status_code'):
                logger.error(f"[Jira Test]     Status Code: {e.status_code}")
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
