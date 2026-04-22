import pandas as pd
import logging
import requests
import time
import re
from datetime import datetime
from connectors.base import BaseConnector
from jira import JIRAError
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

class JiraV3NotSupportedError(Exception):
    """Raised when v3 API is not available (on-premises with v2 only)."""
    pass

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
            # Check if this is a v3-specific 404 on search endpoint
            if 'search/jql' in context.lower():
                return (
                    "Jira API endpoint not found. Your Jira instance may not support the v3 API. "
                    "Try selecting 'Force v2' in the project configuration if you're on an older Jira version."
                )
            return (
                f"Jira project or resource not found. {context} "
                "Please check the project key and try again."
            )
        elif status == 400:
            return (
                f"Invalid Jira request. {context} "
                "Check your project key and configuration."
            )
        elif status == 429:
            return (
                "Jira rate limit exceeded. The system will automatically retry up to 3 times with backoff. "
                "If this keeps happening, increase the 'Request Delay' setting in your project configuration to 200-500ms. "
                "Jira allows 4 requests per 60 seconds by default."
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
            "Jira rejected the request: the API endpoint is not available. "
            "This can happen if your Jira is still on an older API version. "
            "Try selecting 'Force v2' in the project configuration, or ensure your Jira is up to date."
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
    def __init__(self, config: dict, workflow_steps: list, since=None):
        super().__init__(config, workflow_steps, since=since)
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

    def _resolve_api_version(self) -> str:
        """Resolve which Jira API version to use: v3, v2, or auto-detect.
        
        Returns:
            'v3' or 'v2'
        """
        configured_version = self.config.get("jira_api_version", "auto")
        logger.debug(f"[Jira API] Configured version: {configured_version}")
        
        # If explicitly set to v2 or v3, use that
        if configured_version in ("v2", "v3"):
            logger.info(f"[Jira API] Using explicitly configured version: {configured_version}")
            return configured_version
        
        # Auto-detect: try v3 first
        logger.debug("[Jira API] Auto-detecting: attempting v3 first")
        try:
            # Test v3 with a simple endpoint that requires no project knowledge
            url = f"{self.config['url'].rstrip('/')}/rest/api/3/myself"
            jira = self._get_client()
            # Note: ResilientSession handles timeout internally, don't override it
            resp = jira._session.get(url)
            
            logger.debug(f"[Jira API] v3 test returned status {resp.status_code}")
            
            if resp.status_code == 200:
                logger.info("[Jira API] Auto-detected v3 API available")
                return "v3"
            elif resp.status_code == 302:
                # 302 redirect to login page means auth failed or v3 not available
                logger.warning(f"[Jira API] v3 endpoint returned 302 redirect, assuming v2-only instance")
                raise JiraV3NotSupportedError("v3 API returned 302 redirect")
            elif resp.status_code in (404, 410):
                # 404/410 suggests v3 not available
                logger.warning(f"[Jira API] v3 endpoint returned {resp.status_code}, assuming v2-only instance")
                raise JiraV3NotSupportedError(f"v3 API returned {resp.status_code}")
            else:
                # Other 4xx/5xx status codes should be surfaced to user (auth/permission errors)
                logger.warning(f"[Jira API] v3 endpoint returned {resp.status_code}, treating as error")
                resp.raise_for_status()
        except (JiraV3NotSupportedError, JIRAError) as e:
            if isinstance(e, JiraV3NotSupportedError):
                logger.info("[Jira API] v3 not supported, falling back to v2")
                return "v2"
            # For other JIRAErrors, re-raise (auth/permission issues, not version)
            logger.debug(f"[Jira API] JIRAError during v3 test: {e}")
            raise
        except Exception as e:
            # For non-version errors (network, SSL, timeout), don't assume v2
            logger.debug(f"[Jira API] Non-version error during v3 test: {type(e).__name__}: {e}")
            raise

    def _retry_with_rate_limit_backoff(self, func, *args, max_retries=3, **kwargs):
        """Retry a function with automatic backoff for Jira rate limiting (429 errors).
        
        Handles HTTP 429 responses by:
        1. Extracting Retry-After header or default wait time
        2. Waiting the specified duration
        3. Retrying the request
        
        Args:
            func: Callable to retry
            *args: Positional arguments for func
            max_retries: Maximum number of retry attempts (default: 3)
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func if successful
            
        Raises:
            JIRAError: If all retries are exhausted or other errors occur
        """
        import re
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except JIRAError as e:
                if e.status_code == 429:
                    if attempt < max_retries:
                        # Extract retry-after time from error or use default exponential backoff
                        retry_after = 5 + (2 ** attempt)  # 5, 7, 11, 19 seconds
                        error_text = str(e)
                        
                        # Try to extract Retry-After from error message
                        if "after" in error_text.lower():
                            try:
                                match = re.search(r'after\s+(\d+)\s+seconds', error_text.lower())
                                if match:
                                    retry_after = int(match.group(1))
                            except Exception:
                                pass  # Use default backoff
                        
                        logger.warning(
                            f"[Jira Rate Limit] Hit rate limit (429). "
                            f"Attempt {attempt + 1}/{max_retries + 1}. "
                            f"Waiting {retry_after} seconds before retry..."
                        )
                        time.sleep(retry_after)
                        continue
                    else:
                        logger.error(
                            f"[Jira Rate Limit] Exhausted retries after {max_retries} attempts. "
                            f"Rate limit error: {e}"
                        )
                        raise
                else:
                    # Non-429 errors should not be retried
                    raise
            except Exception as e:
                # Non-JIRAError exceptions should not be retried
                raise

    def _search_issues_v2(self, jql: str, start: int, batch: int) -> dict:
        """Call Jira Server/Data Center REST API v2 /search.
        
        Normalizes v2 response to match v3 structure (used by fetch_items).
        """
        url = f"{self.config['url'].rstrip('/')}/rest/api/2/search"
        params = {
            "jql": jql,
            "startAt": start,
            "maxResults": batch,
            "expand": "changelog",
            "fields": "*all",
        }
        
        jira = self._get_client()
        
        logger.debug(f"[Jira Search v2] >>> REQUEST")
        logger.debug(f"[Jira Search v2]     URL: {url}")
        logger.debug(f"[Jira Search v2]     Params: startAt={start}, maxResults={batch}")
        
        try:
            resp = jira._session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            logger.debug(f"[Jira Search v2] <<< RESPONSE")
            logger.debug(f"[Jira Search v2]     Status: {resp.status_code}")
            logger.debug(f"[Jira Search v2]     Issues Count: {len(data.get('issues', []))}")
            
            # Surface any Jira application-level errors embedded in 200 response
            if "errorMessages" in data and data["errorMessages"]:
                logger.error(f"[Jira Search v2] Jira application error: {data['errorMessages']}")
                raise JIRAError(status_code=400, text="; ".join(data["errorMessages"]))
            
            return data
        except Exception as e:
            logger.error(f"[Jira Search v2] Error: {type(e).__name__}: {str(e)}")
            raise

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

    def _fetch_all_issues(self, search_method, jql: str) -> list:
        """Helper to fetch all issues using the given search method.
        
        Args:
            search_method: Either _search_issues_v3 or _search_issues_v2
            jql: The JQL query string
            
        Returns:
            List of all issues (paginated)
        """
        all_issues = []
        start = 0
        batch = 100
        
        # Get request delay from config (default 100ms)
        request_delay_ms = int(self.config.get("request_delay_ms", 100))
        request_delay_sec = request_delay_ms / 1000.0

        while True:
            data = self._retry_with_rate_limit_backoff(search_method, jql, start, batch)
            issues = data.get("issues", [])
            if not issues:
                break
            all_issues.extend(issues)
            if len(issues) < batch:
                break
            start += batch
            # Add delay between requests to avoid rate limiting
            if request_delay_sec > 0:
                time.sleep(request_delay_sec)
        
        return all_issues

    def test_connection(self) -> dict:
        logger.info(f"[Jira Test] Starting connection test with auth_type: {self.config.get('auth_type')}")
        logger.debug(f"[Jira Test] URL: {self.config.get('url')}")
        try:
            # Resolve API version first
            api_version = self._resolve_api_version()
            configured_version = self.config.get("jira_api_version", "auto")
            logger.info(f"[Jira Test] Using API v{api_version} (configured: {configured_version})")
            
            # Use appropriate endpoints based on API version
            try:
                if api_version == "v3":
                    return self._test_connection_v3()
                else:  # v2
                    return self._test_connection_v2()
            except JiraV3NotSupportedError as e:
                # If v3 test failed because v3 not supported, only fallback if auto-detect
                # If user explicitly forced v3, re-raise the error
                if configured_version == "auto":
                    logger.warning(f"[Jira Test] v3 connection failed (auto-detected): {e}, falling back to v2")
                    return self._test_connection_v2()
                else:
                    # User explicitly selected v3, don't fallback
                    logger.error(f"[Jira Test] v3 connection failed (forced): {e}")
                    raise
        except Exception as e:
            logger.error(f"[Jira Test] <<< ERROR")
            logger.error(f"[Jira Test]     Exception Type: {type(e).__name__}")
            logger.error(f"[Jira Test]     Message: {str(e)}")
            if hasattr(e, 'status_code'):
                logger.error(f"[Jira Test]     Status Code: {e.status_code}")
            user_message = _format_jira_error(e, context="during connection test")
            logger.error(f"[Jira Test] ❌ Connection failed: {type(e).__name__}: {str(e)}", exc_info=True)
            return {"success": False, "message": user_message, "boards": [], "api_version_detected": None}

    def _test_connection_v3(self) -> dict:
        """Test connection using v3 API endpoints."""
        logger.debug("[Jira Test v3] Testing v3 endpoints")
        auth_type = self.config.get("auth_type", "api_token")
        
        if auth_type == "personal_access_token":
            # For PAT, use Bearer token with jira client's ResilientSession
            logger.debug("[Jira Test v3] Using PAT token with Bearer authorization")
            
            jira = self._get_client()
            
            try:
                # Test myself endpoint
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/myself"
                logger.debug(f"[Jira Test v3] >>> REQUEST (myself endpoint)")
                
                resp = jira._session.get(url)
                resp.raise_for_status()
                user = resp.json()
                logger.info(f"[Jira Test v3] ✅ Authenticated as: {user.get('displayName', 'Unknown')}")
                
                # Now fetch projects with same auth method
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/projects"
                logger.debug(f"[Jira Test v3] >>> REQUEST (projects endpoint)")
                
                resp = jira._session.get(url)
                resp.raise_for_status()
                data = resp.json()
                projects = data.get('values', [])
                logger.debug(f"[Jira Test v3]     Projects Count: {len(projects)}")
                
                return {
                    "success": True,
                    "message": f"Connected successfully (API v3). Found {len(projects)} projects.",
                    "boards": [{"id": p.get("key"), "name": p.get("name")} for p in projects],
                    "api_version_detected": "v3"
                }
            except JIRAError as e:
                # If projects endpoint returns 404, it might be v3-specific endpoint issue
                if getattr(e, 'status_code', None) == 404 and '/projects' in str(e):
                    logger.warning(f"[Jira Test v3] /rest/api/3/projects returned 404, might not be v3")
                    raise JiraV3NotSupportedError("v3 projects endpoint returned 404")
                # Other 404s (like /myself) indicate auth issues, re-raise
                logger.debug(f"[Jira Test v3] JIRAError: {e}")
                raise
        else:
            # API token auth - also use v3 endpoints directly
            logger.debug("[Jira Test v3] Using API token auth (Basic Auth) with v3 endpoints")
            jira = self._get_client()
            
            try:
                # Test myself endpoint
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/myself"
                logger.debug(f"[Jira Test v3] >>> REQUEST (myself endpoint)")
                
                resp = jira._session.get(url)
                resp.raise_for_status()
                user = resp.json()
                logger.info(f"[Jira Test v3] ✅ Authenticated as: {user.get('displayName', 'Unknown')}")
                
                # Now fetch projects with v3 API
                url = f"{self.config['url'].rstrip('/')}/rest/api/3/projects"
                logger.debug(f"[Jira Test v3] >>> REQUEST (projects endpoint)")
                
                resp = jira._session.get(url)
                resp.raise_for_status()
                data = resp.json()
                projects = data.get('values', [])
                logger.debug(f"[Jira Test v3]     Projects Count: {len(projects)}")
                
                return {
                    "success": True,
                    "message": f"Connected successfully (API v3). Found {len(projects)} projects.",
                    "boards": [{"id": p.get("key"), "name": p.get("name")} for p in projects],
                    "api_version_detected": "v3"
                }
            except JIRAError as e:
                # If projects endpoint returns 404, it might be v3-specific endpoint issue
                if getattr(e, 'status_code', None) == 404 and '/projects' in str(e):
                    logger.warning(f"[Jira Test v3] /rest/api/3/projects returned 404, might not be v3")
                    raise JiraV3NotSupportedError("v3 projects endpoint returned 404")
                # Other 404s (like /myself) indicate auth issues, re-raise
                logger.debug(f"[Jira Test v3] JIRAError: {e}")
                raise

    def _test_connection_v2(self) -> dict:
        """Test connection using v2 API endpoints."""
        logger.debug("[Jira Test v2] Testing v2 endpoints")
        jira = self._get_client()
        
        # Use the jira library which supports v2
        try:
            projects = jira.projects()
            logger.debug(f"[Jira Test v2]     Projects Count: {len(projects)}")
            logger.info(f"[Jira Test v2] ✅ Connected successfully (API v2). Found {len(projects)} projects")
            
            return {
                "success": True,
                "message": f"Connected successfully (API v2). Found {len(projects)} projects.",
                "boards": [{"id": p.key, "name": p.name} for p in projects],
                "api_version_detected": "v2"
            }
        except Exception as e:
            logger.error(f"[Jira Test v2] Error: {type(e).__name__}: {str(e)}")
            raise


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
        base_jql = self.config.get("jql", f"project = {project_key} ORDER BY updated DESC")
        
        # For incremental syncs, add updated timestamp filter
        jql = base_jql
        if self.since:
            # Format datetime for JQL: 2026-04-20 21:00 (no seconds - Jira v2 API requirement)
            since_str = self.since.strftime("%Y-%m-%d %H:%M")
            # Add filter for updated since last sync (insert before ORDER BY if present)
            since_filter = f"updated >= '{since_str}'"
            
            # Check if JQL has ORDER BY clause
            if "ORDER BY" in base_jql.upper():
                # Insert the filter before ORDER BY
                parts = base_jql.upper().split("ORDER BY")
                jql = parts[0].rstrip() + f" AND {since_filter} ORDER BY " + parts[1].strip()
            else:
                # Just append if no ORDER BY
                jql = f"{base_jql} AND {since_filter}"
            logger.info(f"[Jira Fetch] Incremental sync since {since_str}")
        else:
            logger.info(f"[Jira Fetch] Full sync (no previous sync found)")

        status_map = self._build_status_map()
        step_names = [s["display_name"] for s in self.workflow_steps]

        # Resolve API version once at start (not per-batch)
        api_version = self._resolve_api_version()
        logger.info(f"[Jira Fetch] Using API v{api_version} for data fetch")
        
        configured_version = self.config.get("jira_api_version", "auto")
        
        # Try the selected API version, fallback to v2 if v3 fails and auto-detect was used
        try:
            search_method = self._search_issues_v3 if api_version == "v3" else self._search_issues_v2
            all_issues = self._fetch_all_issues(search_method, jql)
        except JiraV3NotSupportedError as e:
            # If v3 fails and auto-detect was used, try v2
            if configured_version == "auto":
                logger.warning(f"[Jira Fetch] v3 search failed (auto-detected): {e}, falling back to v2")
                all_issues = self._fetch_all_issues(self._search_issues_v2, jql)
            else:
                # User explicitly selected v3, don't fallback
                logger.error(f"[Jira Fetch] v3 search failed (forced): {e}")
                raise

        records = []
        for issue in all_issues:
            fields = issue.get("fields", {})
            changelog = issue.get("changelog", {})
            timestamps = {name: None for name in step_names}

            # Collect ALL status transitions for storage (raw, un-mapped)
            raw_transitions: list = []

            # Synthetic initial transition: Jira changelog only records changes, not
            # the starting state. Add a transition at created_at using current status.
            created_at_ts = fields.get("created")
            initial_status = (fields.get("status") or {}).get("name")
            if initial_status and created_at_ts:
                raw_transitions.append({
                    "from_status": None,
                    "to_status": initial_status,
                    "transitioned_at": created_at_ts,
                })

            # Determine if changelog is truncated (Jira may return only ~100 entries)
            histories = changelog.get("histories", [])
            cl_total = changelog.get("total", len(histories))
            if cl_total > len(histories):
                # Paginate the full changelog from the per-issue endpoint
                histories = self._fetch_full_changelog(issue["key"])

            for history in histories:
                created = pd.to_datetime(history["created"])
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        from_status = item.get("fromString")
                        to_raw = item.get("toString") or ""
                        raw_transitions.append({
                            "from_status": from_status,
                            "to_status": to_raw,
                            "transitioned_at": history["created"],
                        })
                        to_lower = to_raw.lower()
                        step_name = status_map.get(to_lower)
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
                "status_transitions": raw_transitions,
            }

            start_steps = [s for s in self.workflow_steps if s["stage"] == "start"]
            in_flight_steps = [s for s in self.workflow_steps if s["stage"] == "in_flight"]
            done_steps = [s for s in self.workflow_steps if s["stage"] == "done"]

            if done_steps:
                done_col = done_steps[-1]["display_name"]
                done_ts = timestamps.get(done_col)
                
                # Cycle time: from start step, or first in_flight step, to done step
                start_ts = None
                if start_steps:
                    start_col = start_steps[0]["display_name"]
                    start_ts = timestamps.get(start_col)
                
                # Fallback to first in_flight step if start step not reached
                if not start_ts and in_flight_steps:
                    in_flight_col = in_flight_steps[0]["display_name"]
                    start_ts = timestamps.get(in_flight_col)
                
                if start_ts and done_ts:
                    record["cycle_time_days"] = (done_ts - start_ts).days
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

    def _fetch_full_changelog(self, issue_key: str) -> list:
        """Paginate /rest/api/2/issue/{key}/changelog to retrieve all history entries.

        The search API with expand=changelog may return only the last ~100 entries.
        This method fetches the complete history when that happens.
        """
        jira = self._get_client()
        base_url = self.config["url"].rstrip("/")
        url = f"{base_url}/rest/api/2/issue/{issue_key}/changelog"
        all_histories: list = []
        start = 0
        batch = 100

        while True:
            params = {"startAt": start, "maxResults": batch}
            try:
                resp = self._retry_with_rate_limit_backoff(
                    lambda p=params: jira._session.get(url, params=p)
                )
                data = resp.json()
            except Exception:
                logger.warning("[Jira Changelog] Failed to paginate changelog for %s, using partial data", issue_key)
                break

            values = data.get("values", [])
            all_histories.extend(values)
            if len(values) < batch or len(all_histories) >= data.get("total", 0):
                break
            start += batch

        return all_histories
