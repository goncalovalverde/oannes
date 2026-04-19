#!/usr/bin/env python3
"""Debug PAT authentication directly."""

import requests
import base64

jira_url = input("Jira URL (e.g., https://atc.bmwgroup.net/jira): ").strip()
pat_token = input("Personal Access Token: ").strip()

print("\n" + "=" * 70)
print("Testing PAT Authentication")
print("=" * 70)

# Test 1: Basic auth with empty username
print("\n[Test 1] Basic auth with empty username + PAT token")
try:
    resp = requests.get(
        f"{jira_url}/rest/api/3/myself",
        auth=('', pat_token),
        timeout=10
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"✅ SUCCESS: {resp.json().get('displayName')}")
    else:
        print(f"❌ FAILED: {resp.status_code}")
        if resp.text:
            print(f"Response: {resp.text[:200]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Basic auth with "token" as username
print("\n[Test 2] Basic auth with 'token' as username + PAT token")
try:
    resp = requests.get(
        f"{jira_url}/rest/api/3/myself",
        auth=('token', pat_token),
        timeout=10
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"✅ SUCCESS: {resp.json().get('displayName')}")
    else:
        print(f"❌ FAILED: {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Bearer token
print("\n[Test 3] Bearer token in Authorization header")
try:
    headers = {"Authorization": f"Bearer {pat_token}"}
    resp = requests.get(
        f"{jira_url}/rest/api/3/myself",
        headers=headers,
        timeout=10
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"✅ SUCCESS: {resp.json().get('displayName')}")
    else:
        print(f"❌ FAILED: {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Verify the auth header being sent
print("\n[Test 4] Debug: What auth header are we sending?")
print(f"PAT Token length: {len(pat_token)}")
print(f"PAT Token first 10 chars: {pat_token[:10]}...")
encoded = base64.b64encode(f':{pat_token}'.encode()).decode()
print(f"Basic auth header (empty user): Basic {encoded[:30]}...")
