import os
import requests
import base64
import logging
import re
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class TextToSpeechService:
    """
    Google Cloud TTS Integration (REST API).
    Uses the Billing-Enabled Key (`GOOGLE_TTS_API_KEY`).
    """
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_TTS_API_KEY")
        self.endpoint = "https://texttospeech.googleapis.com/v1/text:synthesize"
        # Voice Configuration
        # Chrome/Android: "en-US-Journey-F" (Warm Female)
        # Safari Fix: This ensures consistency.
        # Soft/Empathetic American English Configuration
        self.voice_config = {
            "languageCode": "en-US",
            "name": "en-US-Journey-F", # "Sarah" - Warm, Empathetic, Expressive
            "ssmlGender": "FEMALE"
        }
        self.audio_config = {
            "audioEncoding": "MP3",
            "pitch": 0.0,
            "speakingRate": 0.95 # Slightly slower for a more calming effect
        }

    async def generate_audio(self, text: str):
        """
        Converts text to MP3 audio using Google Cloud TTS.
        Returns: Base64 encoded audio string (ready for HTML audio tag).
        """
        if not self.api_key:
            logger.error("GOOGLE_TTS_API_KEY missing. Audio disabled.")
            return None

        # Clean Text (Strip Markdown)
        clean_text = self.clean_text_for_tts(text)

        payload = {
            "input": {"text": clean_text},
            "voice": self.voice_config,
            "audioConfig": self.audio_config
        }

        try:
            # Using synchronous requests in async wrapper for now (low volume)
            # Or use aiohttp if we want to be pure async.
            # To be safe in existing stack, we'll just use requests with a timeout.
            response = requests.post(
                f"{self.endpoint}?key={self.api_key}",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                # API returns { "audioContent": "base64String..." }
                data = response.json()
                return data.get("audioContent")
            else:
                logger.error(f"TTS API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"TTS Exception: {e}")
            return None

    def clean_text_for_tts(self, text: str) -> str:
        """
        Removes Markdown formatting for better speech synthesis.
        - Removes bold (**text**) -> text
        - Removes headers (### Header) -> Header
        - Removes links ([Link](URL)) -> Link
        """
        # Remove bold/italic (** or *)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        
        # Remove headers (#)
        text = re.sub(r'#+\s*', '', text)
        
        # Remove Links ([text](url)) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        return text

    def set_voice_accent(self, locale: str):
        """
        Switch accent dynamically.
        Supported: 'en-US', 'fr-FR' (French Accent trick), 'en-GB'.
        """
        if locale == "fr-FR":
            # French Accent Trick: Use a French Neural voice but speak English
            self.voice_config["languageCode"] = "fr-FR"
            self.voice_config["name"] = "fr-FR-Neural2-A"
        elif locale == "en-GB":
            self.voice_config["languageCode"] = "en-GB"
            self.voice_config["name"] = "en-GB-Neural2-A"
        else:
            # Default Sarah
            self.voice_config["languageCode"] = "en-US"
            self.voice_config["name"] = "en-US-Journey-F"
