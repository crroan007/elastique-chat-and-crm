"""
Elastique CRM - Layer 2 API Test Suite
========================================
Tests all new API endpoints added to crm_router.py

Run: python tests/test_api_endpoints.py
"""

import requests
import json
import uuid
from datetime import datetime

BASE_URL = "http://localhost:8000/api/crm"

def test_endpoint(method, path, data=None, expected_status=200):
    """Helper to test an endpoint"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        elif method == "DELETE":
            response = requests.delete(url, timeout=5)
        elif method == "PATCH":
            response = requests.patch(url, json=data, timeout=5)
        
        passed = response.status_code == expected_status
        return passed, response.status_code, response.json() if response.text else None
    except requests.exceptions.ConnectionError:
        return False, 0, "Connection refused - is server running?"
    except Exception as e:
        return False, 0, str(e)


def run_tests():
    print("=" * 60)
    print("ELASTIQUE CRM - LAYER 2 API TESTS")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    results = []
    
    # ===========================================
    # 1. CONTACT ENDPOINTS
    # ===========================================
    print("\n--- Contact Endpoints ---")
    
    passed, status, data = test_endpoint("GET", "/contacts?limit=5")
    results.append(("GET /contacts", passed, status))
    print(f"  {'PASS' if passed else 'FAIL'} GET /contacts ({status})")
    
    # Get first contact ID for further tests
    contact_id = None
    if passed and isinstance(data, list) and len(data) > 0:
        contact_id = data[0].get("id")
        print(f"       Using contact: {contact_id[:8]}...")
    
    if contact_id:
        passed, status, data = test_endpoint("GET", f"/contacts/{contact_id}")
        results.append(("GET /contacts/:id", passed, status))
        print(f"  {'PASS' if passed else 'FAIL'} GET /contacts/:id ({status})")
    
    # ===========================================
    # 2. TAG ENDPOINTS
    # ===========================================
    print("\n--- Tag Endpoints ---")
    
    if contact_id:
        test_tag = f"api_test_{uuid.uuid4().hex[:6]}"
        
        # Add tag
        passed, status, data = test_endpoint("POST", f"/contacts/{contact_id}/tags", {"tag": test_tag})
        results.append(("POST /contacts/:id/tags", passed, status))
        print(f"  {'PASS' if passed else 'FAIL'} POST /contacts/:id/tags ({status})")
        
        # Get tags
        passed, status, data = test_endpoint("GET", f"/contacts/{contact_id}/tags")
        results.append(("GET /contacts/:id/tags", passed, status))
        print(f"  {'PASS' if passed else 'FAIL'} GET /contacts/:id/tags ({status})")
        
        # Delete tag
        passed, status, data = test_endpoint("DELETE", f"/contacts/{contact_id}/tags/{test_tag}")
        results.append(("DELETE /contacts/:id/tags/:tag", passed, status))
        print(f"  {'PASS' if passed else 'FAIL'} DELETE /contacts/:id/tags/:tag ({status})")
    
    # ===========================================
    # 3. PIPELINE ENDPOINTS
    # ===========================================
    print("\n--- Pipeline Endpoints ---")
    
    passed, status, data = test_endpoint("GET", "/pipelines")
    results.append(("GET /pipelines", passed, status))
    print(f"  {'PASS' if passed else 'FAIL'} GET /pipelines ({status})")
    
    pipeline_id = None
    if passed and isinstance(data, list) and len(data) > 0:
        pipeline_id = data[0].get("id")
        
        passed, status, data = test_endpoint("GET", f"/pipelines/{pipeline_id}")
        results.append(("GET /pipelines/:id", passed, status))
        print(f"  {'PASS' if passed else 'FAIL'} GET /pipelines/:id ({status})")
        if passed:
            print(f"       Pipeline '{data.get('name')}' has {len(data.get('stages', []))} stages")
    
    # ===========================================
    # 4. WORKFLOW ENDPOINTS
    # ===========================================
    print("\n--- Workflow Endpoints ---")
    
    # List workflows
    passed, status, data = test_endpoint("GET", "/workflows")
    results.append(("GET /workflows", passed, status))
    print(f"  {'PASS' if passed else 'FAIL'} GET /workflows ({status})")
    
    # Create workflow
    test_workflow = {
        "name": f"API Test Workflow {uuid.uuid4().hex[:6]}",
        "trigger_type": "event",
        "trigger_event": "contact.created",
        "steps": [
            {"action_type": "add_tag", "config": {"tag": "from_api"}}
        ]
    }
    passed, status, data = test_endpoint("POST", "/workflows", test_workflow)
    results.append(("POST /workflows", passed, status))
    print(f"  {'PASS' if passed else 'FAIL'} POST /workflows ({status})")
    
    workflow_id = data.get("id") if passed else None
    
    if workflow_id:
        # Get workflow
        passed, status, data = test_endpoint("GET", f"/workflows/{workflow_id}")
        results.append(("GET /workflows/:id", passed, status))
        print(f"  {'PASS' if passed else 'FAIL'} GET /workflows/:id ({status})")
        
        # Trigger workflow
        if contact_id:
            passed, status, data = test_endpoint("POST", f"/workflows/{workflow_id}/trigger", 
                                                  {"contact_id": contact_id})
            results.append(("POST /workflows/:id/trigger", passed, status))
            print(f"  {'PASS' if passed else 'FAIL'} POST /workflows/:id/trigger ({status})")
            
            # Get executions
            passed, status, data = test_endpoint("GET", f"/workflows/{workflow_id}/executions")
            results.append(("GET /workflows/:id/executions", passed, status))
            print(f"  {'PASS' if passed else 'FAIL'} GET /workflows/:id/executions ({status})")
    
    # ===========================================
    # 5. EMAIL TEMPLATE ENDPOINTS
    # ===========================================
    print("\n--- Email Template Endpoints ---")
    
    passed, status, data = test_endpoint("GET", "/email-templates")
    results.append(("GET /email-templates", passed, status))
    print(f"  {'PASS' if passed else 'FAIL'} GET /email-templates ({status})")
    
    # ===========================================
    # SUMMARY
    # ===========================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for r in results if r[1])
    failed_count = len(results) - passed_count
    
    print(f"\nTotal Tests: {len(results)}")
    print(f"Passed:      {passed_count}")
    print(f"Failed:      {failed_count}")
    
    pct = (passed_count / len(results)) * 100 if results else 0
    if pct >= 95: grade = "A+"
    elif pct >= 90: grade = "A"
    elif pct >= 85: grade = "B+"
    elif pct >= 80: grade = "B"
    elif pct >= 70: grade = "C"
    else: grade = "F"
    
    print(f"Pass Rate:   {pct:.1f}%")
    print(f"\nGRADE: {grade}")
    
    if failed_count > 0:
        print("\nFailed tests:")
        for name, passed, status in results:
            if not passed:
                print(f"  - {name} (status: {status})")
    
    return passed_count, len(results), grade


if __name__ == "__main__":
    run_tests()
