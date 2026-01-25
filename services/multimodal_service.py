import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logging.warning("GOOGLE_API_KEY not found in .env. Multimodal features will be disabled.")

logger = logging.getLogger(__name__)

class MultimodalService:
    """
    Service for handling Audio, Vision, and Identity extraction using Gemini 1.5 Flash.
    """
    def __init__(self):
        self.model = None
        if API_KEY:
            try:
                # Use Flash for speed and cost effectiveness
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("Gemini 1.5 Flash initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("MultimodalService running in MOCK mode (No API Key).")

    async def analyze_media(self, file_path: str, mime_type: str, prompt: str = "Describe this medical condition.") -> str:
        """
        Generic handler for Audio, Image, and Video.
        Uploads file to Gemini -> Generates Content.
        """
        if not self.model:
            return "[System: Gemini API Key missing. Mock Response.]"

        try:
            logger.info(f"Uploading {file_path} ({mime_type}) to Gemini...")
            
            # 1. Upload File
            uploaded_file = genai.upload_file(path=file_path, mime_type=mime_type)
            
            # 2. Generate Content
            # Gemini handles the file reference natively
            response = self.model.generate_content([prompt, uploaded_file])
            
            return response.text
        except Exception as e:
            logger.error(f"Gemini Analysis Failed: {e}")
            return f"[Error processing media: {str(e)}]"

    async def extract_identity(self, user_text: str) -> dict:
        """
        Uses Gemini to intelligently extract Name and Email, avoiding "Yes" bugs.
        Returns JSON-like dict: {"name": "...", "email": "..."}
        """
        if not self.model:
            # Fallback for mock mode (or if key is missing)
            return {"name": None, "email": None}

        try:
            prompt = f"""
            Extract the user's First Name and Email from this text: "{user_text}"
            
            Rules:
            1. If the name is unclear or just an affirmation (Yes, No, Sure), return null.
            2. If only email is present, return null for name.
            3. Return ONLY a JSON string: {{"name": "...", "email": "..."}}
            """
            
            response = self.model.generate_content(prompt)
            # Simple cleanup to ensure we get dict-compatible string
            cleaned = response.text.replace("```json", "").replace("```", "").strip()
            import json
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Identity Extraction Failed: {e}")
            return {"name": None, "email": None}

    # Compatibility Wrappers for existing Server calls
    async def transcribe_audio(self, file_path: str) -> str:
        return await self.analyze_media(file_path, "audio/mp3", "Transcribe this audio exactly. Do not add descriptions.")

    async def analyze_image(self, file_path: str) -> str:
        return await self.analyze_media(file_path, "image/jpeg", "Act as a medical assistant. Analyze this image for signs of swelling, lymphedema, or injury. Be concise.")
