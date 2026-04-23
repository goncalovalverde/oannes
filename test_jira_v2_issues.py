#!/usr/bin/env python3
"""Diagnostic script to test Jira v2 API issue fetching."""

import sys
import logging
sys.path.insert(0, '/Users/ctw02858/dev/oannes/backend')

# Enable DEBUG logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from connectors import get_connector
from models.connector_config import validate_connector_config

# Test configuration - update these with your actual values
test_config = {
    'url': 'https://atc.bmwgroup.net/jira/',
    'auth_type': 'personal_access_token',
    'personal_access_token': 'YOUR_PAT_TOKEN_HERE',  # Replace with actual token
    'project_key': 'PNC',
    'jira_api_version': 'v2',  # Force v2
}

print("=" * 80)
print("JIRA V2 DIAGNOSTIC TEST")
print("=" * 80)

try:
    # Normalize config
    print("\n1. Normalizing configuration...")
    normalized_config = validate_connector_config('jira', test_config)
    print(f"   ✓ Config normalized successfully")
    print(f"   URL: {normalized_config.get('jira_url')}")
    print(f"   Auth: {normalized_config.get('auth_type')}")
    print(f"   API Version: {normalized_config.get('api_version')}")
    print(f"   Project: {normalized_config.get('project_key')}")
    
    # Create connector
    print("\n2. Creating Jira connector...")
    connector = get_connector('jira', test_config, [
        {'display_name': 'To Do', 'stage': 'todo', 'source_statuses': ['To Do']},
        {'display_name': 'In Progress', 'stage': 'in_progress', 'source_statuses': ['In Progress']},
        {'display_name': 'Done', 'stage': 'done', 'source_statuses': ['Done']},
    ])
    print(f"   ✓ Connector created")
    
    # Test connection
    print("\n3. Testing connection...")
    result = connector.test_connection()
    print(f"   Success: {result['success']}")
    print(f"   Message: {result['message']}")
    if result['success']:
        print(f"   API Version Detected: {result.get('api_version_detected')}")
        print(f"   Boards/Projects: {result.get('boards', [])}")
    
    # Test JQL generation
    print("\n4. Testing JQL generation...")
    base_jql = f"project = {normalized_config.get('project_key')} ORDER BY updated DESC"
    print(f"   Base JQL: {base_jql}")
    
    # Test v2 search
    print("\n5. Testing v2 search endpoint...")
    print(f"   Calling _search_issues_v2 with:")
    print(f"     JQL: {base_jql}")
    print(f"     Start: 0")
    print(f"     Batch: 100")
    
    response = connector._search_issues_v2(base_jql, 0, 100)
    
    print(f"\n   Response received:")
    print(f"     Total issues in project: {response.get('total')}")
    print(f"     Issues in this batch: {len(response.get('issues', []))}")
    
    if response.get('issues'):
        print(f"\n   First issue:")
        issue = response['issues'][0]
        print(f"     Key: {issue.get('key')}")
        print(f"     Summary: {issue.get('fields', {}).get('summary')}")
    else:
        print(f"\n   ⚠️  No issues returned!")
        print(f"   Response keys: {response.keys()}")
        
        # Debug: Try without ORDER BY
        print(f"\n6. Debugging: Trying without ORDER BY clause...")
        simple_jql = f"project = {normalized_config.get('project_key')}"
        print(f"   Simplified JQL: {simple_jql}")
        response2 = connector._search_issues_v2(simple_jql, 0, 100)
        print(f"   Issues found: {len(response2.get('issues', []))}")
        print(f"   Total: {response2.get('total')}")

except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
