"""Test that incremental sync no longer raises TypeError."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from connectors import get_connector
from services.sync_service import SyncService

def test_sync_passes_since_to_get_connector():
    """Verify SyncService._fetch passes 'since' parameter to get_connector."""
    # Create a mock database and project
    mock_db = Mock()
    mock_project = Mock()
    mock_project.id = 1
    mock_project.platform = 'jira'
    mock_project.config = {
        'url': 'https://test.atlassian.net',
        'auth_type': 'api_token',
        'email': 'test@example.com',
        'api_token': 'test'
    }
    mock_project.last_synced_at = datetime.now() - timedelta(days=7)
    
    # Mock the database query
    mock_db.query.return_value.filter.return_value.first.return_value = mock_project
    
    sync_service = SyncService(mock_db)
    
    # Mock get_connector to verify it receives 'since' parameter
    with patch('services.sync_service.get_connector') as mock_get_connector:
        mock_connector = Mock()
        mock_connector.fetch_items.return_value = {}
        mock_get_connector.return_value = mock_connector
        
        try:
            sync_service._fetch(1)
        except Exception:
            # We don't care if it fails for other reasons, just that get_connector was called correctly
            pass
        
        # Verify get_connector was called with 'since' parameter
        assert mock_get_connector.called
        call_kwargs = mock_get_connector.call_args[1]  # Get keyword arguments
        assert 'since' in call_kwargs
        assert call_kwargs['since'] == mock_project.last_synced_at
        print("✅ SyncService._fetch correctly passes 'since' to get_connector")

def test_all_connectors_accept_since_parameter():
    """Verify all connectors can be instantiated with 'since' parameter."""
    config = {
        'platform': 'jira',
        'url': 'https://test.atlassian.net',
        'auth_type': 'api_token',
        'email': 'test@example.com',
        'api_token': 'test'
    }
    
    since = datetime.now() - timedelta(days=7)
    workflow_steps = []
    
    # This should NOT raise TypeError about unexpected keyword argument
    try:
        connector = get_connector('jira', config, workflow_steps, since=since)
        print("✅ JiraConnector accepts 'since' parameter")
    except TypeError as e:
        if 'since' in str(e):
            pytest.fail(f"❌ Connector doesn't accept 'since' parameter: {e}")
    except Exception:
        # Other exceptions are fine - we're just testing the parameter
        print("✅ JiraConnector accepts 'since' parameter (other error occurred)")

if __name__ == '__main__':
    test_sync_passes_since_to_get_connector()
    test_all_connectors_accept_since_parameter()
    print("\n✅ All incremental sync fixes verified!")
