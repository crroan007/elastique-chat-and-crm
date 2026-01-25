"""
Elastique CRM - Workflow Service
=================================
Event-driven automation engine inspired by Twenty's architecture.

Core patterns:
- WorkflowAction interface with execute() method
- WorkflowActionFactory for creating action handlers
- WorkflowExecutor for step-by-step execution
- WorkflowContext for shared state

Author: CTO (2026-01-23)
"""

import sqlite3
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

DB_PATH = "data/elastique.db"


# =============================================
# CONTEXT & RESULT TYPES
# =============================================

@dataclass
class WorkflowContext:
    """Shared context passed through all workflow steps"""
    workflow_id: str
    execution_id: str
    contact_id: str
    trigger_event: str
    trigger_data: Dict = field(default_factory=dict)
    variables: Dict = field(default_factory=dict)
    current_step: int = 0
    
    def set_variable(self, key: str, value: Any):
        self.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)
    
    def to_dict(self) -> Dict:
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "contact_id": self.contact_id,
            "trigger_event": self.trigger_event,
            "trigger_data": self.trigger_data,
            "variables": self.variables,
            "current_step": self.current_step
        }


@dataclass
class ActionResult:
    """Result of executing a workflow action"""
    success: bool
    data: Dict = field(default_factory=dict)
    error: Optional[str] = None
    next_step: Optional[int] = None  # For branching (conditions)
    delay_until: Optional[datetime] = None  # For wait actions


# =============================================
# WORKFLOW ACTION INTERFACE (Twenty pattern)
# =============================================

class WorkflowAction(ABC):
    """Base class for all workflow actions"""
    
    @property
    @abstractmethod
    def action_type(self) -> str:
        """Unique identifier for this action type"""
        pass
    
    @abstractmethod
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        """Execute the action and return result"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """Validate action configuration"""
        pass


# =============================================
# CONCRETE ACTION IMPLEMENTATIONS
# =============================================

class UpdateContactAction(WorkflowAction):
    """Update contact fields"""
    
    @property
    def action_type(self) -> str:
        return "update_contact"
    
    def validate_config(self, config: Dict) -> bool:
        return "updates" in config and isinstance(config["updates"], dict)
    
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        try:
            updates = config.get("updates", {})
            if not updates:
                return ActionResult(success=True, data={"message": "No updates specified"})
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Build UPDATE statement
            set_clauses = []
            values = []
            for field, value in updates.items():
                # Prevent SQL injection by only allowing known fields
                allowed_fields = ["lifecycle_stage", "engagement_score", "last_seen_at", "notes"]
                if field in allowed_fields:
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
            
            if set_clauses:
                values.append(context.contact_id)
                cursor.execute(
                    f"UPDATE contacts SET {', '.join(set_clauses)} WHERE id = ?",
                    values
                )
                conn.commit()
            
            conn.close()
            return ActionResult(success=True, data={"updated_fields": list(updates.keys())})
        except Exception as e:
            return ActionResult(success=False, error=str(e))


class AddToSegmentAction(WorkflowAction):
    """Add contact to a segment"""
    
    @property
    def action_type(self) -> str:
        return "add_to_segment"
    
    def validate_config(self, config: Dict) -> bool:
        return "segment_id" in config
    
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        try:
            segment_id = config["segment_id"]
            
            # Log to timeline that contact was added to segment
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO timeline_events (id, contact_id, event_type, summary, occurred_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                context.contact_id,
                "segment_added",
                f"Added to segment by workflow",
                datetime.now().isoformat(),
                "workflow"
            ))
            
            conn.commit()
            conn.close()
            
            return ActionResult(success=True, data={"segment_id": segment_id})
        except Exception as e:
            return ActionResult(success=False, error=str(e))


class AddTagAction(WorkflowAction):
    """Add a tag to the contact"""
    
    @property
    def action_type(self) -> str:
        return "add_tag"
    
    def validate_config(self, config: Dict) -> bool:
        return "tag" in config
    
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        try:
            tag = config["tag"]
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Check if tag already exists
            cursor.execute(
                "SELECT id FROM contact_tags WHERE contact_id = ? AND tag = ?",
                (context.contact_id, tag)
            )
            if cursor.fetchone():
                conn.close()
                return ActionResult(success=True, data={"message": "Tag already exists"})
            
            # Add the tag
            cursor.execute("""
                INSERT INTO contact_tags (id, contact_id, tag, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                context.contact_id,
                tag,
                "workflow",
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            return ActionResult(success=True, data={"tag": tag})
        except Exception as e:
            return ActionResult(success=False, error=str(e))


class WaitAction(WorkflowAction):
    """Delay workflow execution"""
    
    @property
    def action_type(self) -> str:
        return "wait"
    
    def validate_config(self, config: Dict) -> bool:
        return "duration_minutes" in config
    
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        minutes = config.get("duration_minutes", 60)
        delay_until = datetime.now() + timedelta(minutes=minutes)
        
        return ActionResult(
            success=True,
            data={"wait_minutes": minutes},
            delay_until=delay_until
        )


class ConditionAction(WorkflowAction):
    """Branch based on condition"""
    
    @property
    def action_type(self) -> str:
        return "condition"
    
    def validate_config(self, config: Dict) -> bool:
        return "condition" in config and "then_step" in config
    
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        try:
            condition = config["condition"]
            then_step = config["then_step"]
            else_step = config.get("else_step")
            
            # Evaluate condition
            # Simple field matching for now
            field = condition.get("field")
            operator = condition.get("operator", "equals")
            value = condition.get("value")
            
            # Get contact field value
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(f"SELECT {field} FROM contacts WHERE id = ?", (context.contact_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return ActionResult(success=False, error="Contact not found")
            
            actual_value = row[0]
            
            # Evaluate
            condition_met = False
            if operator == "equals":
                condition_met = actual_value == value
            elif operator == "not_equals":
                condition_met = actual_value != value
            elif operator == "greater_than":
                condition_met = float(actual_value or 0) > float(value)
            elif operator == "less_than":
                condition_met = float(actual_value or 0) < float(value)
            elif operator == "contains":
                condition_met = value in str(actual_value or "")
            
            next_step = then_step if condition_met else else_step
            
            return ActionResult(
                success=True,
                data={"condition_met": condition_met},
                next_step=next_step
            )
        except Exception as e:
            return ActionResult(success=False, error=str(e))


class CreateNoteAction(WorkflowAction):
    """Create a note on the contact"""
    
    @property
    def action_type(self) -> str:
        return "create_note"
    
    def validate_config(self, config: Dict) -> bool:
        return "content" in config
    
    def execute(self, context: WorkflowContext, config: Dict) -> ActionResult:
        try:
            content = config["content"]
            
            # Variable substitution
            for key, value in context.variables.items():
                content = content.replace(f"{{{key}}}", str(value))
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO contact_notes (id, contact_id, content, author_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                context.contact_id,
                content,
                "workflow",
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            return ActionResult(success=True, data={"note_created": True})
        except Exception as e:
            return ActionResult(success=False, error=str(e))


# =============================================
# ACTION FACTORY (Twenty pattern)
# =============================================

class WorkflowActionFactory:
    """Factory to create action handlers by type"""
    
    _actions: Dict[str, type] = {
        "update_contact": UpdateContactAction,
        "add_to_segment": AddToSegmentAction,
        "add_tag": AddTagAction,
        "wait": WaitAction,
        "condition": ConditionAction,
        "create_note": CreateNoteAction,
    }
    
    @classmethod
    def get_action(cls, action_type: str) -> Optional[WorkflowAction]:
        action_class = cls._actions.get(action_type)
        if action_class:
            return action_class()
        return None
    
    @classmethod
    def list_action_types(cls) -> List[str]:
        return list(cls._actions.keys())
    
    @classmethod
    def register_action(cls, action_type: str, action_class: type):
        cls._actions[action_type] = action_class


# =============================================
# WORKFLOW EXECUTOR
# =============================================

class WorkflowExecutor:
    """Executes workflows step-by-step"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.factory = WorkflowActionFactory
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
    
    def start_execution(self, workflow_id: str, contact_id: str, trigger_event: str, trigger_data: Dict = None) -> str:
        """Start a new workflow execution"""
        execution_id = str(uuid.uuid4())
        
        context = WorkflowContext(
            workflow_id=workflow_id,
            execution_id=execution_id,
            contact_id=contact_id,
            trigger_event=trigger_event,
            trigger_data=trigger_data or {}
        )
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO workflow_executions 
            (id, workflow_id, contact_id, trigger_event, trigger_data, started_at, status, current_step, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution_id,
            workflow_id,
            contact_id,
            trigger_event,
            json.dumps(trigger_data or {}),
            datetime.now().isoformat(),
            "running",
            0,
            json.dumps(context.to_dict())
        ))
        
        conn.commit()
        conn.close()
        
        # Execute the workflow
        self._execute_workflow(context)
        
        return execution_id
    
    def _execute_workflow(self, context: WorkflowContext):
        """Execute all steps in the workflow"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get workflow steps
        cursor.execute("""
            SELECT id, step_order, action_type, action_config, condition_logic
            FROM workflow_steps
            WHERE workflow_id = ?
            ORDER BY step_order
        """, (context.workflow_id,))
        
        steps = cursor.fetchall()
        
        current_step = context.current_step
        
        while current_step < len(steps):
            step = steps[current_step]
            step_id, step_order, action_type, action_config_str, condition_logic_str = step
            
            action_config = json.loads(action_config_str or "{}")
            
            # Get action handler
            action = self.factory.get_action(action_type)
            if not action:
                self._fail_execution(context, f"Unknown action type: {action_type}")
                conn.close()
                return
            
            # Execute action
            result = action.execute(context, action_config)
            
            if not result.success:
                self._fail_execution(context, result.error)
                conn.close()
                return
            
            # Handle delay
            if result.delay_until:
                # TODO: Schedule delayed continuation
                self._update_execution(context, "waiting", current_step)
                conn.close()
                return
            
            # Handle branching
            if result.next_step is not None:
                current_step = result.next_step
            else:
                current_step += 1
            
            context.current_step = current_step
        
        # Workflow completed
        self._complete_execution(context)
        conn.close()
    
    def _update_execution(self, context: WorkflowContext, status: str, step: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE workflow_executions 
            SET status = ?, current_step = ?, context = ?
            WHERE id = ?
        """, (status, step, json.dumps(context.to_dict()), context.execution_id))
        conn.commit()
        conn.close()
    
    def _complete_execution(self, context: WorkflowContext):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE workflow_executions 
            SET status = ?, completed_at = ?, current_step = ?, context = ?
            WHERE id = ?
        """, ("completed", datetime.now().isoformat(), context.current_step, 
              json.dumps(context.to_dict()), context.execution_id))
        conn.commit()
        conn.close()
    
    def _fail_execution(self, context: WorkflowContext, error: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE workflow_executions 
            SET status = ?, completed_at = ?, error_message = ?
            WHERE id = ?
        """, ("failed", datetime.now().isoformat(), error, context.execution_id))
        conn.commit()
        conn.close()


# =============================================
# WORKFLOW SERVICE (CRUD + Execution)
# =============================================

class WorkflowService:
    """High-level service for workflow management"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.executor = WorkflowExecutor(db_path)
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
    
    def create_workflow(self, name: str, trigger_type: str, trigger_event: str = None, 
                       description: str = None, steps: List[Dict] = None) -> str:
        """Create a new workflow"""
        workflow_id = str(uuid.uuid4())
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO workflows (id, name, description, trigger_type, trigger_event, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            workflow_id, name, description, trigger_type, trigger_event,
            datetime.now().isoformat(), datetime.now().isoformat()
        ))
        
        # Add steps
        if steps:
            for i, step in enumerate(steps):
                cursor.execute("""
                    INSERT INTO workflow_steps (id, workflow_id, step_order, action_type, action_config, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    workflow_id,
                    i,
                    step.get("action_type"),
                    json.dumps(step.get("config", {})),
                    datetime.now().isoformat()
                ))
        
        conn.commit()
        conn.close()
        
        return workflow_id
    
    def list_workflows(self, include_inactive: bool = False) -> List[Dict]:
        """List all workflows"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = "SELECT id, name, description, trigger_type, trigger_event, is_active, created_at FROM workflows"
        if not include_inactive:
            query += " WHERE is_active = 1"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "trigger_type": row[3],
                "trigger_event": row[4],
                "is_active": bool(row[5]),
                "created_at": row[6]
            }
            for row in rows
        ]
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow with steps"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, trigger_type, trigger_event, is_active, is_published, version
            FROM workflows WHERE id = ?
        """, (workflow_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # Get steps
        cursor.execute("""
            SELECT id, step_order, action_type, action_config
            FROM workflow_steps WHERE workflow_id = ? ORDER BY step_order
        """, (workflow_id,))
        steps = cursor.fetchall()
        
        conn.close()
        
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "trigger_type": row[3],
            "trigger_event": row[4],
            "is_active": bool(row[5]),
            "is_published": bool(row[6]),
            "version": row[7],
            "steps": [
                {
                    "id": s[0],
                    "step_order": s[1],
                    "action_type": s[2],
                    "config": json.loads(s[3] or "{}")
                }
                for s in steps
            ]
        }
    
    def trigger_workflow(self, workflow_id: str, contact_id: str, trigger_data: Dict = None) -> str:
        """Trigger a workflow execution"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        if not workflow["is_active"]:
            raise ValueError(f"Workflow is inactive: {workflow_id}")
        
        return self.executor.start_execution(
            workflow_id=workflow_id,
            contact_id=contact_id,
            trigger_event=workflow["trigger_event"] or "manual",
            trigger_data=trigger_data
        )
    
    def get_executions(self, workflow_id: str = None, contact_id: str = None, limit: int = 50) -> List[Dict]:
        """Get workflow executions"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = "SELECT id, workflow_id, contact_id, trigger_event, started_at, completed_at, status, error_message FROM workflow_executions"
        conditions = []
        params = []
        
        if workflow_id:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)
        if contact_id:
            conditions.append("contact_id = ?")
            params.append(contact_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY started_at DESC LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": row[0],
                "workflow_id": row[1],
                "contact_id": row[2],
                "trigger_event": row[3],
                "started_at": row[4],
                "completed_at": row[5],
                "status": row[6],
                "error_message": row[7]
            }
            for row in rows
        ]


# =============================================
# TEST / DEMO
# =============================================

if __name__ == "__main__":
    print("=" * 50)
    print("WORKFLOW SERVICE TEST")
    print("=" * 50)
    
    service = WorkflowService()
    
    # Create a test workflow
    workflow_id = service.create_workflow(
        name="Welcome New Lead",
        trigger_type="event",
        trigger_event="contact.created",
        description="Welcomes new leads with a tag and note",
        steps=[
            {"action_type": "add_tag", "config": {"tag": "new_lead"}},
            {"action_type": "create_note", "config": {"content": "New lead created via workflow"}},
            {"action_type": "update_contact", "config": {"updates": {"lifecycle_stage": "lead"}}}
        ]
    )
    print(f"\n✓ Created workflow: {workflow_id}")
    
    # List workflows
    workflows = service.list_workflows()
    print(f"\n✓ Found {len(workflows)} workflows")
    
    # Get workflow details
    workflow = service.get_workflow(workflow_id)
    print(f"\n✓ Workflow '{workflow['name']}' has {len(workflow['steps'])} steps:")
    for step in workflow['steps']:
        print(f"  - {step['action_type']}")
    
    print("\n✅ WorkflowService is ready!")
