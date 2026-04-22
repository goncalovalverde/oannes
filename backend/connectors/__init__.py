"""Connector factory using a registry pattern (Open/Closed Principle).

Adding a new connector never requires modifying this file — just add an entry
to the REGISTRY dict below (or call register_connector at import time).
"""
from datetime import datetime
from typing import Optional
from connectors.base import BaseConnector
from models.connector_config import validate_connector_config

# Maps platform identifier → (module_path, class_name)
_REGISTRY: dict[str, tuple[str, str]] = {
    "jira":         ("connectors.jira",          "JiraConnector"),
    "trello":       ("connectors.trello",         "TrelloConnector"),
    "azure_devops": ("connectors.azure_devops",   "AzureDevOpsConnector"),
    "gitlab":       ("connectors.gitlab",         "GitLabConnector"),
    "linear":       ("connectors.linear",         "LinearConnector"),
    "shortcut":     ("connectors.shortcut",       "ShortcutConnector"),
    "csv":          ("connectors.csv_connector",  "CSVConnector"),
}


def register_connector(platform: str, module: str, class_name: str) -> None:
    """Register a third-party or plugin connector at runtime."""
    _REGISTRY[platform] = (module, class_name)


def get_connector(platform: str, config: dict, workflow_steps: list, since: Optional[datetime] = None) -> BaseConnector:
    """Get a connector instance with validated configuration.
    
    Args:
        platform: Connector platform (jira, csv, trello, etc.)
        config: Configuration dictionary (validated before use)
        workflow_steps: Workflow step definitions
        since: Optional datetime for incremental sync
        
    Returns:
        Instantiated connector with validated config
        
    Raises:
        ValueError: If platform unknown or config invalid
    """
    if platform not in _REGISTRY:
        raise ValueError(f"Unknown platform: {platform!r}. Registered: {sorted(_REGISTRY)}")

    # Validate config for this platform
    validated_config = validate_connector_config(platform, config)

    module_path, class_name = _REGISTRY[platform]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(validated_config, workflow_steps, since=since)


def supported_platforms() -> list[str]:
    return sorted(_REGISTRY)
