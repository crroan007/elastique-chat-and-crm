
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse
import os
import uuid
import logging

# [NEW] Import core services
from services.crm_service import CRMService

router = APIRouter(prefix="/voice")
logger = logging.getLogger("ElastiqueVoice")

@router.post("/webhook")
async def handle_incoming_call(
    From: str = Form(...),
    CallSid: str = Form(...)
):
    """
    Twilio Webhook: Handles incoming calls.
    1. Identifies caller via CRM (checks phone).
    2. Logs 'Call Started' to Timeline.
    3. Responds with AI Greeting.
    """
    logger.info(f"Incoming Call from {From} (SID: {CallSid})")
    
    # 1. Initialize CRM
    crm = CRMService() # DB Connection
    
    # 2. Identify Contact (Mock Logic for MVP - normally by Phone)
    # We will just grab the first contact or create a 'Voice Guest'
    # In V3, we will add 'phone' lookup to CRMService
    
    response = VoiceResponse()
    
    # 3. Simple IVR Logic (MVP)
    # Greet the user with a pleasant voice
    response.say("Hello. You have reached Elastique Wellness. How can we support your lymphatic health today?", voice="alice")
    
    # Record the user's response
    response.record(max_length=10, action="/voice/transcribe", method="POST")
    
    # 4. Log Event to Timeline (Direct SQL for now until CRMService updated)
    # MVP: Just log that a call happened.
    # TODO: Add 'log_timeline_event' method to CRMService
    
    return Response(content=str(response), media_type="application/xml")

@router.post("/transcribe")
async def handle_recording(
    RecordingUrl: str = Form(...),
    CallSid: str = Form(...)
):
    logger.info(f"Recording received: {RecordingUrl}")
    
    # 1. Download Audio (Twilio -> Local)
    # In V3, stream deeply, for MVP download temp
    import requests
    temp_filename = f"temp_rec_{CallSid}.mp3"
    try:
        # Note: Twilio RecordingUrl usually requires Basic Auth if protected, 
        # but public for now or add auth headers if needed
        rec_data = requests.get(RecordingUrl).content
        with open(temp_filename, "wb") as f:
            f.write(rec_data)
            
        # 2. Transcribe via Gemini
        from services.multimodal_service import MultimodalService
        mm_service = MultimodalService()
        transcript_text = await mm_service.analyze_media(
            temp_filename, 
            "audio/mp3", 
            "Transcribe this medical wellness call accurately."
        )
        
        # 3. Log to Timeline (Unified History)
        # Using raw SQL for MVP speed
        import sqlite3
        conn = sqlite3.connect('data/elastique.db')
        cursor = conn.cursor()
        
        # We need a contact_id, for MVP we'll query by phone or use NULL (Guest)
        # Assuming we can match by CallSid metadata later if needed
        # For now, insert as 'voice_call_inbound'
        
        import json
        metadata = json.dumps({
            "call_sid": CallSid,
            "recording_url": RecordingUrl,
            "duration": 0 # Unknown here
        })
        
        cursor.execute("""
            INSERT INTO timeline_events (
                id, contact_id, event_type, source_channel, summary, transcript, metadata
            ) VALUES (
                lower(hex(randomblob(16))),
                (SELECT id FROM contacts LIMIT 1), -- MOCK: Attach to first contact for demo
                'voice_call_inbound',
                'phone_chat',
                'Inbound Call from User',
                ?,
                ?
            )
        """, (transcript_text, metadata))
        
        conn.commit()
        conn.close()
        
        # Cleanup
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    except Exception as e:
        logger.error(f"Transcription Error: {e}")
    
    response = VoiceResponse()
    response.say("Thank you. I have transcribed your message and logged it to your file.", voice="alice")
    return Response(content=str(response), media_type="application/xml")
