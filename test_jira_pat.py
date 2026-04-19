#!/usr/bin/env python3
"""
Test script for Jira PAT authentication debugging.

Usage:
    python test_jira_pat.py

You'll be prompted to enter your Jira details.
"""

import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_jira_pat():
    """Test Jira PAT authentication."""
    from connectors.jira import JiraConnector
    import traceback
    
    print("\n" + "=" * 70)
    print("JIRA PAT AUTHENTICATION TEST")
    print("=" * 70)
    
    # Get user input
    jira_url = input("\n🔵 Jira URL (e.g., https://atc.bmwgroup.net/jira): ").strip()
    pat_token = input("🔑 Personal Access Token: ").strip()
    
    if not jira_url or not pat_token:
        print("\n❌ URL and token are required!")
        return
    
    print("\n⏳ Testing connection...")
    print("-" * 70)
    
    try:
        config = {
            'url': jira_url,
            'auth_type': 'personal_access_token',
            'personal_access_token': pat_token,
            'project_key': 'TEST'  # Optional, for testing
        }
        
        connector = JiraConnector(config, [])
        result = connector.test_connection()
        
        print("\n" + "=" * 70)
        if result['success']:
            print("✅ CONNECTION SUCCESSFUL!")
            print("=" * 70)
            print(f"\nMessage: {result['message']}")
            if result.get('boards'):
                print(f"\n📋 Found {len(result['boards'])} projects:")
                for board in result['boards']:
                    print(f"   - {board['id']}: {board['name']}")
        else:
            print("❌ CONNECTION FAILED!")
            print("=" * 70)
            print(f"\nError: {result['message']}")
            
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ EXCEPTION OCCURRED!")
        print("=" * 70)
        print(f"\nException Type: {type(e).__name__}")
        print(f"Exception Message: {str(e)}")
        print("\nFull Traceback:")
        traceback.print_exc()


def test_jira_api_token():
    """Test Jira API token authentication (legacy)."""
    from connectors.jira import JiraConnector
    import traceback
    
    print("\n" + "=" * 70)
    print("JIRA API TOKEN AUTHENTICATION TEST (Legacy)")
    print("=" * 70)
    
    # Get user input
    jira_url = input("\n🔵 Jira URL (e.g., https://yourcompany.atlassian.net): ").strip()
    email = input("📧 Email: ").strip()
    api_token = input("🔑 API Token: ").strip()
    
    if not jira_url or not email or not api_token:
        print("\n❌ URL, email, and token are required!")
        return
    
    print("\n⏳ Testing connection...")
    print("-" * 70)
    
    try:
        config = {
            'url': jira_url,
            'auth_type': 'api_token',
            'email': email,
            'api_token': api_token,
            'project_key': 'TEST'  # Optional, for testing
        }
        
        connector = JiraConnector(config, [])
        result = connector.test_connection()
        
        print("\n" + "=" * 70)
        if result['success']:
            print("✅ CONNECTION SUCCESSFUL!")
            print("=" * 70)
            print(f"\nMessage: {result['message']}")
            if result.get('boards'):
                print(f"\n📋 Found {len(result['boards'])} projects:")
                for board in result['boards']:
                    print(f"   - {board['id']}: {board['name']}")
        else:
            print("❌ CONNECTION FAILED!")
            print("=" * 70)
            print(f"\nError: {result['message']}")
            
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ EXCEPTION OCCURRED!")
        print("=" * 70)
        print(f"\nException Type: {type(e).__name__}")
        print(f"Exception Message: {str(e)}")
        print("\nFull Traceback:")
        traceback.print_exc()


def main():
    """Main entry point."""
    print("\n🧪 JIRA CONNECTION TESTER\n")
    print("Choose test type:")
    print("  1. Personal Access Token (PAT)")
    print("  2. API Token (Email + Token)")
    print("  0. Exit")
    
    choice = input("\nEnter choice (0-2): ").strip()
    
    if choice == "1":
        test_jira_pat()
    elif choice == "2":
        test_jira_api_token()
    elif choice == "0":
        print("Goodbye!")
        return
    else:
        print("❌ Invalid choice!")
        return
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
