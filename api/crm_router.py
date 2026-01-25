from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from services.crm_service import CRMService
from services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/crm", tags=["CRM"])
crm_service = CRMService()
workflow_service = WorkflowService()

# =============================================
# DATA MODELS (Pydantic)
# =============================================

class NoteCreate(BaseModel):
    content: str
    author_id: str = "manager"

class TicketCreate(BaseModel):
    subject: str
    description: str
    priority: str = "medium"

class DealStageUpdate(BaseModel):
    new_stage: str

class TagCreate(BaseModel):
    tag: str

class WorkflowCreate(BaseModel):
    name: str
    trigger_type: str = "event"
    trigger_event: Optional[str] = None
    description: Optional[str] = None
    steps: List[Dict[str, Any]] = []

class WorkflowTrigger(BaseModel):
    contact_id: str
    trigger_data: Optional[Dict[str, Any]] = None

class WorkflowStepCreate(BaseModel):
    action_type: str
    config: Dict[str, Any] = {}


# =============================================
# CONTACT ENDPOINTS (Existing)
# =============================================

@router.get("/contacts")
def get_contacts_summary(limit: int = 50, lifecycle: Optional[str] = None):
    """
    Returns the lightweight list for the 'Smart List' Grid.
    """
    return crm_service.get_all_contacts_summary(limit=limit, lifecycle_filter=lifecycle)

@router.get("/contacts/{contact_id}")
def get_contact_dossier(contact_id: str):
    """
    Returns the full 'Contact 360' Dossier (Timeline, Identity, etc.)
    """
    dossier = crm_service.get_contact_dossier(contact_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Contact not found")
    return dossier

@router.post("/contacts/{contact_id}/notes")
def add_contact_note(contact_id: str, note: NoteCreate):
    """
    Write-Back: Add a note to the timeline.
    """
    return crm_service.add_note(contact_id, note.content, note.author_id)

@router.post("/contacts/{contact_id}/tickets")
def create_support_ticket(contact_id: str, ticket: TicketCreate):
    """
    Write-Back: Escalation to Support.
    """
    return crm_service.create_ticket(contact_id, ticket.subject, ticket.description, ticket.priority)


# =============================================
# TAG ENDPOINTS (New - Layer 2)
# =============================================

@router.get("/contacts/{contact_id}/tags")
def get_contact_tags(contact_id: str):
    """
    Get all tags for a contact.
    """
    import sqlite3
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, tag, created_by, created_at FROM contact_tags WHERE contact_id = ?", (contact_id,))
    tags = [{"id": r[0], "tag": r[1], "created_by": r[2], "created_at": r[3]} for r in cursor.fetchall()]
    conn.close()
    return {"contact_id": contact_id, "tags": tags}

@router.post("/contacts/{contact_id}/tags")
def add_contact_tag(contact_id: str, tag_data: TagCreate):
    """
    Add a tag to a contact.
    """
    import sqlite3
    import uuid
    from datetime import datetime
    
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    
    # Check if tag already exists
    cursor.execute("SELECT id FROM contact_tags WHERE contact_id = ? AND tag = ?", (contact_id, tag_data.tag))
    if cursor.fetchone():
        conn.close()
        return {"status": "exists", "message": f"Tag '{tag_data.tag}' already exists"}
    
    tag_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO contact_tags (id, contact_id, tag, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (tag_id, contact_id, tag_data.tag, "api", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return {"status": "created", "id": tag_id, "tag": tag_data.tag}

@router.delete("/contacts/{contact_id}/tags/{tag}")
def remove_contact_tag(contact_id: str, tag: str):
    """
    Remove a tag from a contact.
    """
    import sqlite3
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contact_tags WHERE contact_id = ? AND tag = ?", (contact_id, tag))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "deleted", "tag": tag}


# =============================================
# PIPELINE ENDPOINTS (New - Layer 2)
# =============================================

@router.get("/pipelines")
def get_pipelines():
    """
    Get all pipelines with their stages.
    """
    import sqlite3
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, description, is_default, created_at FROM pipelines")
    pipelines = []
    for p in cursor.fetchall():
        cursor.execute("""
            SELECT id, name, color, sort_order, probability, stale_after_days 
            FROM pipeline_stages WHERE pipeline_id = ? ORDER BY sort_order
        """, (p[0],))
        stages = [
            {"id": s[0], "name": s[1], "color": s[2], "sort_order": s[3], "probability": s[4], "stale_after_days": s[5]}
            for s in cursor.fetchall()
        ]
        pipelines.append({
            "id": p[0],
            "name": p[1],
            "description": p[2],
            "is_default": bool(p[3]),
            "created_at": p[4],
            "stages": stages
        })
    
    conn.close()
    return pipelines

@router.get("/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: str):
    """
    Get a specific pipeline with stages.
    """
    import sqlite3
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, description, is_default, created_at FROM pipelines WHERE id = ?", (pipeline_id,))
    p = cursor.fetchone()
    if not p:
        conn.close()
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    cursor.execute("""
        SELECT id, name, color, sort_order, probability, stale_after_days 
        FROM pipeline_stages WHERE pipeline_id = ? ORDER BY sort_order
    """, (pipeline_id,))
    stages = [
        {"id": s[0], "name": s[1], "color": s[2], "sort_order": s[3], "probability": s[4], "stale_after_days": s[5]}
        for s in cursor.fetchall()
    ]
    
    conn.close()
    return {
        "id": p[0],
        "name": p[1],
        "description": p[2],
        "is_default": bool(p[3]),
        "created_at": p[4],
        "stages": stages
    }


# =============================================
# DEAL ENDPOINTS (Enhanced)
# =============================================

@router.patch("/deals/{deal_id}/stage")
def update_deal(deal_id: str, update: DealStageUpdate):
    """
    Write-Back: Move deal pipeline stage (automatically logs history).
    """
    result = crm_service.update_deal_stage(deal_id, update.new_stage)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =============================================
# WORKFLOW ENDPOINTS (New - Layer 2)
# =============================================

@router.get("/workflows")
def list_workflows(include_inactive: bool = False):
    """
    List all workflows.
    """
    return workflow_service.list_workflows(include_inactive=include_inactive)

@router.post("/workflows")
def create_workflow(workflow: WorkflowCreate):
    """
    Create a new workflow with steps.
    """
    workflow_id = workflow_service.create_workflow(
        name=workflow.name,
        trigger_type=workflow.trigger_type,
        trigger_event=workflow.trigger_event,
        description=workflow.description,
        steps=workflow.steps
    )
    return {"status": "created", "id": workflow_id}

@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    """
    Get workflow details with steps.
    """
    workflow = workflow_service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.post("/workflows/{workflow_id}/trigger")
def trigger_workflow(workflow_id: str, trigger: WorkflowTrigger):
    """
    Trigger a workflow execution for a contact.
    """
    try:
        execution_id = workflow_service.trigger_workflow(
            workflow_id=workflow_id,
            contact_id=trigger.contact_id,
            trigger_data=trigger.trigger_data
        )
        return {"status": "triggered", "execution_id": execution_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/workflows/{workflow_id}/executions")
def get_workflow_executions(workflow_id: str, limit: int = 50):
    """
    Get execution history for a workflow.
    """
    return workflow_service.get_executions(workflow_id=workflow_id, limit=limit)

@router.get("/contacts/{contact_id}/workflow-executions")
def get_contact_workflow_executions(contact_id: str, limit: int = 50):
    """
    Get all workflow executions for a specific contact.
    """
    return workflow_service.get_executions(contact_id=contact_id, limit=limit)


# =============================================
# EMAIL TEMPLATE ENDPOINTS (New - Layer 2)
# =============================================

@router.get("/email-templates")
def list_email_templates():
    """
    List all email templates.
    """
    import sqlite3
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, subject, created_at, updated_at FROM email_templates ORDER BY created_at DESC")
    templates = [
        {"id": r[0], "name": r[1], "subject": r[2], "created_at": r[3], "updated_at": r[4]}
        for r in cursor.fetchall()
    ]
    conn.close()
    return templates

@router.get("/email-templates/{template_id}")
def get_email_template(template_id: str):
    """
    Get full email template with body.
    """
    import sqlite3
    conn = sqlite3.connect("data/elastique.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, subject, body_html, body_text, created_at, updated_at FROM email_templates WHERE id = ?", (template_id,))
    r = cursor.fetchone()
    conn.close()
    
    if not r:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": r[0], "name": r[1], "subject": r[2], 
        "body_html": r[3], "body_text": r[4],
        "created_at": r[5], "updated_at": r[6]
    }


# =============================================
# EXTERNAL / PUBLIC API ("Connect API")
# =============================================

@router.get("/public/contacts/{email_or_id}")
def public_get_contact_segmentation(email_or_id: str):
    """
    External API: Allows other apps (Shopify, Email Marketing) to fetch segments/tags.
    In a real app, this would require an API Key.
    """
    return {"status": "ok", "message": "Public Connect API ready", "query": email_or_id}

