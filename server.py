import os
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from dotenv import load_dotenv

# [NEW] Service Imports
# Ensure 'services' module is in path or installed
try:
    from services.citation_engine import CitationEngine
    from services.citation_verifier import CitationVerifier
    from services.protocol_generator import ProtocolGenerator
    from services.conversation_manager import ConversationManager
    from services.analytics_service import AnalyticsService
except ImportError:
    # Fallback for dev environment if path issues
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from services.citation_engine import CitationEngine
    from services.citation_verifier import CitationVerifier
    from services.protocol_generator import ProtocolGenerator
    from services.conversation_manager import ConversationManager
    from services.analytics_service import AnalyticsService

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ElastiqueBot")

app = FastAPI(title="Elastique AI Consultant", version="2.0.0")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [NEW] API Routers
from api.analytics import router as analytics_router
from api.voice_webhook import router as voice_router # [NEW]
from api.crm_router import router as crm_router # [NEW] Admin Dashboard

app.include_router(analytics_router)
app.include_router(voice_router)
app.include_router(crm_router)

# [NEW] Initialize Core Engines
citation_engine = CitationEngine() 
# In production, pass db_string: CitationEngine(os.getenv("DATABASE_URL"))
# citation_engine.load_local_library("scientific_library.json") # Pre-load for now

analytics_service = AnalyticsService(os.getenv("DATABASE_URL")) # Passes None if not set, triggers Console Mode

# Data Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    email: Optional[str] = None # For Identity Resolution
    user_email: Optional[str] = None # Alias for robustness
    visitor_id: Optional[str] = None # Cookie ID

class ProtocolRequest(BaseModel):
    conversation_id: str
    agreed_items: List[str]

@app.on_event("startup")
async def startup_event():
    logger.info("Elastique AI v2.0 Starting...")
    logger.info("Initializing Logic: Protocol First, Citation Backed.")
    # Here we would connect to Supabase
    # await db.connect()

@app.get("/health")
async def health_check():
    return {"status": "active", "version": "2.0.0", "mode": "Science-Backed"}

# Initialize Services
from services.multimodal_service import MultimodalService
from services.tts_service import TextToSpeechService

# Initialize Multimodal Service (Gemini 1.5 Flash)
mm_service = MultimodalService()
tts_service = TextToSpeechService()

# Initialize Conversation Manager with dependencies
conv_manager = ConversationManager(citation_engine, analytics_service, mm_service)

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main Chat Endpoint.
    Uses ConversationManager State Machine.
    Returns Text + Audio (Base64).
    """
    user_msg = request.message
    # Resolve Email (Alias support)
    incoming_email = request.email or request.user_email
    
    # Use session_id if provided, else use email or default
    session_id = request.session_id or incoming_email or "default_session"
    
    # 1. Identity Check (Stub - logic is inside process_turn mostly, or middleware)
    
    # 2. Process Turn via State Machine
    response_text = await conv_manager.process_turn(session_id, user_msg, incoming_email)
    
    # 3. Generate Audio (Async - Optional but Premium)
    audio_base64 = None
    if tts_service:
        # Check if we should use French Accent (Hack)
        # We can pass context later, for now defaults to Sarah (Journey-F)
        audio_base64 = await tts_service.generate_audio(response_text)
    
    # [NEW] Return Identity Metadata for Frontend Persistence
    state = conv_manager.get_state(session_id)
    return {
        "response": response_text, 
        "audio": audio_base64,
        "user_email": state.user_email,
        "user_name": state.user_name
    }

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    session_id: str = Form(...),
    message: Optional[str] = Form(None)
):
    """
    Handle Photo/Audio/Video Uploads + Optional Text Context.
    """
    logger.info(f"Received file: {file.filename} ({file.content_type}) for session: {session_id}")
    
    # 1. Save temp file
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())
        
    # 2. Process via Multimodal Service
    media_context = ""
    
    if not mm_service:
        media_context = f"[System: User uploaded {file.filename} but Multimodal Service is offline]"
    
    elif "audio" in file.content_type:
        # Audio is usually the message itself
        transcription = await mm_service.transcribe_audio(temp_filename)
        media_context = f"[Audio Transcript]: {transcription}"
        logger.info(f"Audio Transcribed: {transcription}")
        
    elif "image" in file.content_type:
        # Prompt LLaVA to describe the medical condition
        description = await mm_service.analyze_image(temp_filename)
        media_context = f"[Photo Analysis]: {description}"
        logger.info(f"Image Analyzed: {description}")
        
    elif "video" in file.content_type:
         media_context = "[System: Video upload received. Video analysis pending implementation.]"

    # 3. Clean up
    if os.path.exists(temp_filename):
        os.remove(temp_filename)

    # 4. Combine Text + Media
    # If user typed "Here is my foot" (message) and uploaded a photo (media_context)
    full_input = ""
    if message:
        full_input = f"{message}\n\n{media_context}"
    else:
        full_input = media_context

    # 5. Trigger Conversation Turn
    # We pass the combined context. DO NOT pass a fake email here; rely on session state.
    response_text = await conv_manager.process_turn(session_id, full_input, user_email=None)
    
    # 6. Generate Audio (Consistency with /chat)
    audio_base64 = None
    if tts_service:
        audio_base64 = await tts_service.generate_audio(response_text)
    
    return {"response": response_text, "audio": audio_base64}

# [NEW] Agentic Analyst Integration
from services.conversation_analyst import ConversationAnalyst
analyst = ConversationAnalyst(mm_service)

@app.post("/chat/end")
async def end_chat_endpoint(request: ChatRequest):
    """
    Triggers the 'End of Session' Agent.
    1. Mark session as resolved (optional).
    2. Run Agentic Analysis (Gemini).
    3. Return structured metrics.
    """
    session_id = request.session_id or request.email
    if not session_id:
        return {"error": "Session ID required"}

    # Run Analysis (Background task in production, immediate here for demo)
    metrics = await analyst.analyze_session(session_id)
    
    return {"status": "analyzed", "metrics": metrics}

# [NEW] Protocol PDF Generation Endpoint
# Initialize Engines
protocol_gen = ProtocolGenerator()

@app.post("/generate-protocol")
async def generate_protocol(req: ProtocolRequest):
    """
    Generates the Personalized Protocol PDF.
    Triggered when user agrees to the lifestyle changes.
    """
    try:
        # In a real app, we fetch User Name/Email from DB using Conversation ID
        # For now, we mock or accept it in request if we updated the model
        # Assuming req has fields or we default
        user_name = "Valued Client" 
        
        pdf_path = protocol_gen.generate_pdf(
            conversation_id=req.conversation_id,
            user_name=user_name,
            root_cause="Identified via Chat Analysis", # TODO: Pass real root cause
            daily_items=[{"action": item, "details": "Daily Commitment"} for item in req.agreed_items],
            weekly_items=[] # Mock for now
        )
        
        # Convert local path to Public URL
        filename = os.path.basename(pdf_path)
        public_url = f"/static/protocols/{filename}" # Relative URL for frontend
        
        return {"pdf_url": public_url}
    except Exception as e:
        logger.error(f"PDF Gen Error: {e}")
        raise HTTPException(status_code=500, detail="Protocol generation failed")

# Mount static files (Widget Assets)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
