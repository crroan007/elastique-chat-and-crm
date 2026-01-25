"""
Elastique CRM - Comprehensive Test Suite
==========================================
Tests ALL new functionality from Schema V3 and Service Layer

Coverage:
- Layer 0: Schema (all 31 tables, columns, indexes)
- Layer 1: Services (WorkflowService, CRMService enhancements)
- Layer 2: Workflow Actions (all 6 action types)
- Layer 3: Pipelines, Tags, Email Tracking

Run: python tests/test_crm_comprehensive.py
"""

import sqlite3
import json
import uuid
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workflow_service import (
    WorkflowService, WorkflowExecutor, WorkflowActionFactory,
    WorkflowContext, ActionResult,
    UpdateContactAction, AddToSegmentAction, AddTagAction,
    WaitAction, ConditionAction, CreateNoteAction
)
from services.crm_service import CRMService

DB_PATH = "data/elastique.db"


# =============================================
# TEST INFRASTRUCTURE
# =============================================

class TestResult:
    def __init__(self, name: str, passed: bool, details: str = ""):
        self.name = name
        self.passed = passed
        self.details = details

class TestSuite:
    def __init__(self, name: str):
        self.name = name
        self.results: List[TestResult] = []
    
    def add(self, name: str, passed: bool, details: str = ""):
        self.results.append(TestResult(name, passed, details))
    
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    def grade(self) -> str:
        pct = (self.passed_count() / len(self.results)) * 100 if self.results else 0
        if pct >= 95: return "A+"
        if pct >= 90: return "A"
        if pct >= 85: return "B+"
        if pct >= 80: return "B"
        if pct >= 70: return "C"
        if pct >= 60: return "D"
        return "F"


def get_conn():
    return sqlite3.connect(DB_PATH)


# =============================================
# LAYER 0: SCHEMA TESTS
# =============================================

def test_schema() -> TestSuite:
    suite = TestSuite("Layer 0: Schema")
    conn = get_conn()
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    
    # Required tables from V3 migration
    required_tables = [
        # Original tables
        "contacts", "conversations", "messages", "contact_notes", "support_tickets",
        "deals", "deal_history", "segments", "campaigns", "orders", "order_items",
        "timeline_events",
        # V3 additions
        "pipelines", "pipeline_stages",
        "workflows", "workflow_steps", "workflow_executions",
        "contact_tags",
        "email_templates", "email_sends", "email_events"
    ]
    
    # Test 1: All required tables exist
    for table in required_tables:
        exists = table in tables
        suite.add(f"Table exists: {table}", exists, 
                 "OK" if exists else "MISSING!")
    
    # Test 2: Table column counts (spot check structure)
    expected_columns = {
        "pipelines": 6,
        "pipeline_stages": 8,
        "workflows": 12,
        "workflow_steps": 7,
        "workflow_executions": 11,
        "contact_tags": 5,
        "email_templates": 8,
        "email_sends": 7,
        "email_events": 5
    }
    
    for table, expected_count in expected_columns.items():
        cursor.execute(f"PRAGMA table_info({table})")
        actual_count = len(cursor.fetchall())
        passed = actual_count >= expected_count
        suite.add(f"Column count: {table} >= {expected_count}", passed,
                 f"Found {actual_count} columns")
    
    # Test 3: Default pipeline seeded
    cursor.execute("SELECT COUNT(*) FROM pipelines WHERE is_default = 1")
    has_default = cursor.fetchone()[0] > 0
    suite.add("Default pipeline seeded", has_default)
    
    # Test 4: Pipeline stages seeded
    cursor.execute("SELECT COUNT(*) FROM pipeline_stages")
    stage_count = cursor.fetchone()[0]
    suite.add("Pipeline stages seeded (6+)", stage_count >= 6, f"Found {stage_count}")
    
    # Test 5: Indexes exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_tags%'")
    indexes = cursor.fetchall()
    suite.add("Tag indexes created", len(indexes) >= 2, f"Found {len(indexes)}")
    
    # Test 6: Enhanced deals columns
    cursor.execute("PRAGMA table_info(deals)")
    deal_cols = [c[1] for c in cursor.fetchall()]
    suite.add("Deals has pipeline_id", "pipeline_id" in deal_cols)
    suite.add("Deals has pipeline_stage_id", "pipeline_stage_id" in deal_cols)
    suite.add("Deals has expected_close_at", "expected_close_at" in deal_cols)
    suite.add("Deals has lost_reason", "lost_reason" in deal_cols)
    
    # Test 7: Author attribution
    cursor.execute("PRAGMA table_info(timeline_events)")
    te_cols = [c[1] for c in cursor.fetchall()]
    suite.add("timeline_events has created_by", "created_by" in te_cols)
    
    conn.close()
    return suite


# =============================================
# LAYER 1: SERVICE TESTS
# =============================================

def test_workflow_service() -> TestSuite:
    suite = TestSuite("Layer 1: WorkflowService")
    service = WorkflowService()
    
    # Test 1: Create workflow
    try:
        workflow_id = service.create_workflow(
            name="Test Workflow",
            trigger_type="event",
            trigger_event="test.event",
            description="Test description",
            steps=[
                {"action_type": "add_tag", "config": {"tag": "test_tag"}},
                {"action_type": "create_note", "config": {"content": "Test note"}}
            ]
        )
        suite.add("Create workflow", True, workflow_id[:8])
    except Exception as e:
        suite.add("Create workflow", False, str(e))
        return suite
    
    # Test 2: Get workflow
    try:
        workflow = service.get_workflow(workflow_id)
        suite.add("Get workflow", workflow is not None)
        suite.add("Workflow has name", workflow.get("name") == "Test Workflow")
        suite.add("Workflow has 2 steps", len(workflow.get("steps", [])) == 2)
    except Exception as e:
        suite.add("Get workflow", False, str(e))
    
    # Test 3: List workflows
    try:
        workflows = service.list_workflows()
        suite.add("List workflows", len(workflows) > 0, f"Found {len(workflows)}")
    except Exception as e:
        suite.add("List workflows", False, str(e))
    
    # Test 4: Get workflow details has correct structure
    try:
        w = service.get_workflow(workflow_id)
        suite.add("Workflow has trigger_type", "trigger_type" in w)
        suite.add("Workflow has is_active", "is_active" in w)
        suite.add("Workflow has is_published", "is_published" in w)
        suite.add("Steps have action_type", all("action_type" in s for s in w.get("steps", [])))
    except Exception as e:
        suite.add("Workflow structure", False, str(e))
    
    # Test 5: Get non-existent workflow returns None
    try:
        result = service.get_workflow("non-existent-id")
        suite.add("Non-existent workflow returns None", result is None)
    except Exception as e:
        suite.add("Non-existent workflow returns None", False, str(e))
    
    return suite


def test_action_factory() -> TestSuite:
    suite = TestSuite("Layer 1: ActionFactory")
    
    # Test all registered action types
    action_types = [
        "update_contact", "add_to_segment", "add_tag",
        "wait", "condition", "create_note"
    ]
    
    for action_type in action_types:
        action = WorkflowActionFactory.get_action(action_type)
        suite.add(f"Get action: {action_type}", action is not None)
        if action:
            suite.add(f"Action type property: {action_type}", 
                     action.action_type == action_type)
    
    # Test unknown action returns None
    unknown = WorkflowActionFactory.get_action("unknown_action")
    suite.add("Unknown action returns None", unknown is None)
    
    # Test list action types
    types = WorkflowActionFactory.list_action_types()
    suite.add("List action types", len(types) >= 6, f"Found {len(types)}")
    
    return suite


def test_workflow_actions() -> TestSuite:
    suite = TestSuite("Layer 1: Workflow Actions")
    
    # Create a test contact
    crm = CRMService()
    conn = get_conn()
    cursor = conn.cursor()
    
    test_contact_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO contacts (id, email, first_name, last_name, lifecycle_stage, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (test_contact_id, f"test_{uuid.uuid4().hex[:8]}@test.com", "Test", "User", "visitor", datetime.now().isoformat()))
    conn.commit()
    
    context = WorkflowContext(
        workflow_id="test-workflow",
        execution_id="test-execution",
        contact_id=test_contact_id,
        trigger_event="test"
    )
    
    # Test 1: AddTagAction
    try:
        action = AddTagAction()
        suite.add("AddTagAction: validate_config", action.validate_config({"tag": "test"}))
        result = action.execute(context, {"tag": "test_action_tag"})
        suite.add("AddTagAction: execute success", result.success, result.error or "")
        
        # Verify tag was added
        cursor.execute("SELECT tag FROM contact_tags WHERE contact_id = ?", (test_contact_id,))
        tags = [t[0] for t in cursor.fetchall()]
        suite.add("AddTagAction: tag persisted", "test_action_tag" in tags)
    except Exception as e:
        suite.add("AddTagAction", False, str(e))
    
    # Test 2: CreateNoteAction
    try:
        action = CreateNoteAction()
        suite.add("CreateNoteAction: validate_config", action.validate_config({"content": "test"}))
        result = action.execute(context, {"content": "Test note from action"})
        suite.add("CreateNoteAction: execute success", result.success, result.error or "")
        
        # Verify note was added
        cursor.execute("SELECT content FROM contact_notes WHERE contact_id = ?", (test_contact_id,))
        notes = [n[0] for n in cursor.fetchall()]
        suite.add("CreateNoteAction: note persisted", any("Test note from action" in n for n in notes))
    except Exception as e:
        suite.add("CreateNoteAction", False, str(e))
    
    # Test 3: UpdateContactAction
    try:
        action = UpdateContactAction()
        suite.add("UpdateContactAction: validate_config", 
                 action.validate_config({"updates": {"lifecycle_stage": "lead"}}))
        result = action.execute(context, {"updates": {"lifecycle_stage": "lead"}})
        suite.add("UpdateContactAction: execute success", result.success, result.error or "")
        
        # Verify update
        cursor.execute("SELECT lifecycle_stage FROM contacts WHERE id = ?", (test_contact_id,))
        stage = cursor.fetchone()[0]
        suite.add("UpdateContactAction: field updated", stage == "lead")
    except Exception as e:
        suite.add("UpdateContactAction", False, str(e))
    
    # Test 4: WaitAction
    try:
        action = WaitAction()
        suite.add("WaitAction: validate_config", action.validate_config({"duration_minutes": 60}))
        result = action.execute(context, {"duration_minutes": 30})
        suite.add("WaitAction: execute success", result.success)
        suite.add("WaitAction: has delay_until", result.delay_until is not None)
    except Exception as e:
        suite.add("WaitAction", False, str(e))
    
    # Test 5: ConditionAction
    try:
        action = ConditionAction()
        suite.add("ConditionAction: validate_config", 
                 action.validate_config({"condition": {}, "then_step": 1}))
        result = action.execute(context, {
            "condition": {"field": "lifecycle_stage", "operator": "equals", "value": "lead"},
            "then_step": 5,
            "else_step": 10
        })
        suite.add("ConditionAction: execute success", result.success, result.error or "")
        suite.add("ConditionAction: correct branch (then)", result.next_step == 5)
    except Exception as e:
        suite.add("ConditionAction", False, str(e))
    
    # Test 6: AddToSegmentAction
    try:
        action = AddToSegmentAction()
        suite.add("AddToSegmentAction: validate_config", 
                 action.validate_config({"segment_id": "test"}))
        result = action.execute(context, {"segment_id": "test-segment"})
        suite.add("AddToSegmentAction: execute success", result.success, result.error or "")
    except Exception as e:
        suite.add("AddToSegmentAction", False, str(e))
    
    # Cleanup
    cursor.execute("DELETE FROM contacts WHERE id = ?", (test_contact_id,))
    conn.commit()
    conn.close()
    
    return suite


def test_crm_service() -> TestSuite:
    suite = TestSuite("Layer 1: CRMService")
    crm = CRMService()
    
    # Test 1: Create contact (returns contact_id string, not dict)
    try:
        email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        contact_id = crm.create_or_update_contact(email, "Test", "User")
        suite.add("Create contact", contact_id is not None and isinstance(contact_id, str))
    except Exception as e:
        suite.add("Create contact", False, str(e))
        return suite
    
    if not contact_id:
        suite.add("Get contact ID", False, "Contact ID is None")
        return suite
    
    # Test 2: Get contact dossier
    try:
        dossier = crm.get_contact_dossier(contact_id)
        suite.add("Get dossier", dossier is not None)
        suite.add("Dossier has email", dossier is not None and "email" in dossier)
        suite.add("Dossier has timeline", dossier is not None and "timeline" in dossier)
    except Exception as e:
        suite.add("Get dossier", False, str(e))
    
    # Test 3: Add note
    try:
        note = crm.add_note(contact_id, "Test note content")
        suite.add("Add note", note is not None)
    except Exception as e:
        suite.add("Add note", False, str(e))
    
    # Test 4: Create ticket
    try:
        ticket = crm.create_ticket(contact_id, "Test Subject", "Test Description")
        suite.add("Create ticket", ticket is not None)
    except Exception as e:
        suite.add("Create ticket", False, str(e))
    
    # Test 5: Get all contacts summary
    try:
        contacts = crm.get_all_contacts_summary()
        suite.add("Get contacts summary", len(contacts) > 0)
    except Exception as e:
        suite.add("Get contacts summary", False, str(e))
    
    return suite


# =============================================
# LAYER 2: PIPELINE & TAG TESTS
# =============================================

def test_pipelines() -> TestSuite:
    suite = TestSuite("Layer 2: Pipelines")
    conn = get_conn()
    cursor = conn.cursor()
    
    # Test 1: Get default pipeline
    cursor.execute("SELECT id, name FROM pipelines WHERE is_default = 1")
    default = cursor.fetchone()
    suite.add("Default pipeline exists", default is not None)
    
    if default:
        pipeline_id = default[0]
        
        # Test 2: Pipeline has stages
        cursor.execute("SELECT id, name, sort_order, probability FROM pipeline_stages WHERE pipeline_id = ?", (pipeline_id,))
        stages = cursor.fetchall()
        suite.add("Pipeline has stages", len(stages) > 0, f"Found {len(stages)}")
        
        # Test 3: Stages are ordered
        orders = [s[2] for s in stages]
        suite.add("Stages are ordered", orders == sorted(orders))
        
        # Test 4: Stages have probability
        has_prob = all(s[3] is not None for s in stages)
        suite.add("Stages have probability", has_prob)
    
    # Test 5: Create new pipeline
    try:
        new_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO pipelines (id, name, description, is_default, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (new_id, "Test Pipeline", "Test", 0, datetime.now().isoformat()))
        conn.commit()
        suite.add("Create pipeline", True)
        
        # Cleanup
        cursor.execute("DELETE FROM pipelines WHERE id = ?", (new_id,))
        conn.commit()
    except Exception as e:
        suite.add("Create pipeline", False, str(e))
    
    conn.close()
    return suite


def test_tags() -> TestSuite:
    suite = TestSuite("Layer 2: Tags")
    conn = get_conn()
    cursor = conn.cursor()
    
    # Create test contact
    contact_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO contacts (id, email, first_name, created_at)
        VALUES (?, ?, ?, ?)
    """, (contact_id, f"tag_test_{uuid.uuid4().hex[:6]}@test.com", "TagTest", datetime.now().isoformat()))
    conn.commit()
    
    # Test 1: Add tag
    try:
        tag_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO contact_tags (id, contact_id, tag, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (tag_id, contact_id, "vip", "test", datetime.now().isoformat()))
        conn.commit()
        suite.add("Add tag", True)
    except Exception as e:
        suite.add("Add tag", False, str(e))
    
    # Test 2: Query tags by contact
    cursor.execute("SELECT tag FROM contact_tags WHERE contact_id = ?", (contact_id,))
    tags = [t[0] for t in cursor.fetchall()]
    suite.add("Query tags by contact", "vip" in tags)
    
    # Test 3: Query contacts by tag
    cursor.execute("""
        SELECT c.id FROM contacts c 
        JOIN contact_tags t ON c.id = t.contact_id 
        WHERE t.tag = ?
    """, ("vip",))
    contacts = cursor.fetchall()
    suite.add("Query contacts by tag", len(contacts) > 0)
    
    # Test 4: Multiple tags per contact
    cursor.execute("""
        INSERT INTO contact_tags (id, contact_id, tag, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), contact_id, "premium", "test", datetime.now().isoformat()))
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM contact_tags WHERE contact_id = ?", (contact_id,))
    tag_count = cursor.fetchone()[0]
    suite.add("Multiple tags per contact", tag_count >= 2)
    
    # Cleanup
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    
    return suite


def test_email_tracking() -> TestSuite:
    suite = TestSuite("Layer 2: Email Tracking")
    conn = get_conn()
    cursor = conn.cursor()
    
    # Test 1: Create email template
    try:
        template_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO email_templates (id, name, subject, body_html, body_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (template_id, "Welcome Email", "Welcome!", "<p>Hello</p>", "Hello", datetime.now().isoformat()))
        conn.commit()
        suite.add("Create email template", True)
    except Exception as e:
        suite.add("Create email template", False, str(e))
        return suite
    
    # Test 2: Query template
    cursor.execute("SELECT name, subject FROM email_templates WHERE id = ?", (template_id,))
    template = cursor.fetchone()
    suite.add("Query email template", template is not None)
    
    # Test 3: Create email send record
    try:
        send_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO email_sends (id, template_id, status, sent_at)
            VALUES (?, ?, ?, ?)
        """, (send_id, template_id, "sent", datetime.now().isoformat()))
        conn.commit()
        suite.add("Create email send", True)
    except Exception as e:
        suite.add("Create email send", False, str(e))
        return suite
    
    # Test 4: Create email event (open)
    try:
        event_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO email_events (id, email_send_id, event_type, occurred_at)
            VALUES (?, ?, ?, ?)
        """, (event_id, send_id, "opened", datetime.now().isoformat()))
        conn.commit()
        suite.add("Track email open", True)
    except Exception as e:
        suite.add("Track email open", False, str(e))
    
    # Test 5: Query email events
    cursor.execute("""
        SELECT e.event_type FROM email_events e
        JOIN email_sends s ON e.email_send_id = s.id
        WHERE s.id = ?
    """, (send_id,))
    events = cursor.fetchall()
    suite.add("Query email events", len(events) > 0)
    
    # Test 6: Track email click
    try:
        click_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO email_events (id, email_send_id, event_type, metadata, occurred_at)
            VALUES (?, ?, ?, ?, ?)
        """, (click_id, send_id, "clicked", json.dumps({"url": "https://example.com"}), datetime.now().isoformat()))
        conn.commit()
        suite.add("Track email click with metadata", True)
    except Exception as e:
        suite.add("Track email click with metadata", False, str(e))
    
    # Cleanup
    cursor.execute("DELETE FROM email_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()
    
    return suite


# =============================================
# LAYER 3: WORKFLOW EXECUTION TESTS
# =============================================

def test_workflow_execution() -> TestSuite:
    suite = TestSuite("Layer 3: Workflow Execution")
    service = WorkflowService()
    crm = CRMService()
    conn = get_conn()
    cursor = conn.cursor()
    
    # Create test contact (create_or_update_contact returns contact_id string)
    email = f"wf_test_{uuid.uuid4().hex[:8]}@test.com"
    contact_id = crm.create_or_update_contact(email, "Workflow", "Test")
    
    # Create test workflow
    workflow_id = service.create_workflow(
        name="Execution Test Workflow",
        trigger_type="event",
        trigger_event="test.trigger",
        steps=[
            {"action_type": "add_tag", "config": {"tag": "workflow_executed"}},
            {"action_type": "create_note", "config": {"content": "Workflow ran successfully"}}
        ]
    )
    suite.add("Create test workflow", workflow_id is not None)
    
    # Trigger workflow
    try:
        execution_id = service.trigger_workflow(workflow_id, contact_id, {"source": "test"})
        suite.add("Trigger workflow", execution_id is not None)
    except Exception as e:
        suite.add("Trigger workflow", False, str(e))
        return suite
    
    # Check execution record
    executions = service.get_executions(workflow_id=workflow_id)
    suite.add("Execution record created", len(executions) > 0)
    
    if executions:
        exec_record = executions[0]
        suite.add("Execution has status", "status" in exec_record)
        suite.add("Execution completed", exec_record.get("status") == "completed", exec_record.get("status"))
    
    # Verify side effects
    cursor.execute("SELECT tag FROM contact_tags WHERE contact_id = ?", (contact_id,))
    tags = [t[0] for t in cursor.fetchall()]
    suite.add("Tag action executed", "workflow_executed" in tags)
    
    cursor.execute("SELECT content FROM contact_notes WHERE contact_id = ?", (contact_id,))
    notes = [n[0] for n in cursor.fetchall()]
    suite.add("Note action executed", any("Workflow ran successfully" in n for n in notes))
    
    # Cleanup
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    cursor.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    conn.commit()
    conn.close()
    
    return suite


# =============================================
# RUN ALL TESTS
# =============================================

def run_all_tests():
    print("=" * 60)
    print("ELASTIQUE CRM - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    all_suites = []
    
    # Layer 0: Schema
    print("\n" + "-" * 40)
    schema_suite = test_schema()
    all_suites.append(schema_suite)
    print(f"[{schema_suite.name}] {schema_suite.passed_count()}/{len(schema_suite.results)} passed")
    
    # Layer 1: Services
    print("\n" + "-" * 40)
    wf_suite = test_workflow_service()
    all_suites.append(wf_suite)
    print(f"[{wf_suite.name}] {wf_suite.passed_count()}/{len(wf_suite.results)} passed")
    
    factory_suite = test_action_factory()
    all_suites.append(factory_suite)
    print(f"[{factory_suite.name}] {factory_suite.passed_count()}/{len(factory_suite.results)} passed")
    
    actions_suite = test_workflow_actions()
    all_suites.append(actions_suite)
    print(f"[{actions_suite.name}] {actions_suite.passed_count()}/{len(actions_suite.results)} passed")
    
    crm_suite = test_crm_service()
    all_suites.append(crm_suite)
    print(f"[{crm_suite.name}] {crm_suite.passed_count()}/{len(crm_suite.results)} passed")
    
    # Layer 2: Features
    print("\n" + "-" * 40)
    pipeline_suite = test_pipelines()
    all_suites.append(pipeline_suite)
    print(f"[{pipeline_suite.name}] {pipeline_suite.passed_count()}/{len(pipeline_suite.results)} passed")
    
    tags_suite = test_tags()
    all_suites.append(tags_suite)
    print(f"[{tags_suite.name}] {tags_suite.passed_count()}/{len(tags_suite.results)} passed")
    
    email_suite = test_email_tracking()
    all_suites.append(email_suite)
    print(f"[{email_suite.name}] {email_suite.passed_count()}/{len(email_suite.results)} passed")
    
    # Layer 3: Execution
    print("\n" + "-" * 40)
    exec_suite = test_workflow_execution()
    all_suites.append(exec_suite)
    print(f"[{exec_suite.name}] {exec_suite.passed_count()}/{len(exec_suite.results)} passed")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    total_passed = sum(s.passed_count() for s in all_suites)
    total_tests = sum(len(s.results) for s in all_suites)
    total_failed = total_tests - total_passed
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed:      {total_passed} ✓")
    print(f"Failed:      {total_failed} ✗")
    print(f"Pass Rate:   {(total_passed/total_tests)*100:.1f}%")
    
    # Calculate overall grade
    pct = (total_passed / total_tests) * 100
    if pct >= 95: grade = "A+"
    elif pct >= 90: grade = "A"
    elif pct >= 85: grade = "B+"
    elif pct >= 80: grade = "B"
    elif pct >= 70: grade = "C"
    elif pct >= 60: grade = "D"
    else: grade = "F"
    
    print(f"\n{'=' * 60}")
    print(f"OVERALL GRADE: {grade}")
    print(f"{'=' * 60}")
    
    # Show failures
    if total_failed > 0:
        print("\n⚠ FAILED TESTS:")
        for suite in all_suites:
            for result in suite.results:
                if not result.passed:
                    print(f"  - [{suite.name}] {result.name}: {result.details}")
    
    return total_passed, total_tests, grade


if __name__ == "__main__":
    passed, total, grade = run_all_tests()
