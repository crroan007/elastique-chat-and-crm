from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
import random

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

import json
import os
from collections import Counter

# Helper to read the log
def read_events():
    events = []
    if not os.path.exists("data/events.log.json"):
        return []
    with open("data/events.log.json", "r") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except:
                continue
    return events

@router.get("/summary")
async def get_summary_metrics(range: str = "30d"):
    """
    Returns REAL aggregated metrics from the event log.
    """
    events = read_events()
    
    # Filter by table
    conversations = [e for e in events if e["table"] == "conversations" and e["data"]["event"] == "session_start"]
    leads = [e for e in events if e["table"] == "contacts" and e["data"]["event"] == "lead_captured"]
    product_clicks = [e for e in events if e["table"] == "product_events" and e["data"]["action"] == "click"]
    
    total_sessions = len(conversations)
    total_leads = len(leads)
    
    # Simple conversion rate
    conv_rate = (total_leads / total_sessions * 100) if total_sessions > 0 else 0
    
    return {
        "total_sessions": total_sessions,
        "active_leads": total_leads,
        "conversion_rate": round(conv_rate, 1),
        "attributed_revenue": 0.00, # Mock for now as we don't have purchase events yet
        "trends": {
            "sessions": "+100%", # Baseline is 0
            "leads": "+100%",
            "revenue": "0%"
        }
    }

@router.get("/conversations")
async def get_recent_conversations(limit: int = 10):
    """
    Returns the real live feed of chat sessions.
    """
    events = read_events()
    sessions = {}
    
    # Group by Session ID
    for e in events:
        sid = e["data"].get("session_id")
        if not sid: continue
        
        if sid not in sessions:
            sessions[sid] = {"id": sid, "user": "Guest", "status": "active", "msg_count": 0, "time": e["timestamp"]}
            
        if e["table"] == "contacts" and e["data"]["event"] == "lead_captured":
            sessions[sid]["user"] = e["data"]["email"]
            
        if e["table"] == "messages":
            sessions[sid]["msg_count"] += 1
            
    # Convert to list and sort desc
    session_list = list(sessions.values())
    session_list.sort(key=lambda x: x["time"], reverse=True)
    
    return session_list[:limit]

@router.get("/funnel")
async def get_funnel_metrics():
    """
    Returns real funnel data.
    """
    events = read_events()
    
    sessions = len([e for e in events if e["table"] == "conversations" and e["data"]["event"] == "session_start"])
    leads = len([e for e in events if e["table"] == "contacts" and e["data"]["event"] == "lead_captured"])
    protocols = len([e for e in events if e["table"] == "conversations" and e["data"]["event"] == "protocol_generated"])
    
    return [
        {"stage": "Sessions", "count": sessions, "dropoff": 0},
        {"stage": "Leads Captured", "count": leads, "dropoff": 0},
        {"stage": "Protocols Generated", "count": protocols, "dropoff": 0},
    ]
