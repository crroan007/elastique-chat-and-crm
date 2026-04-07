import json
import os
import re
from typing import Optional, Dict

from services.redaction import redact_phi

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class DecisionRouter:
    """
    Lightweight judgment layer for discovery and agreement handling.
    Uses a stronger model for intent and constraint classification.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = os.getenv("LLM_ROUTER_ENABLED", "true").lower() == "true"
        self.model = os.getenv("LLM_ROUTER_MODEL", "gpt-4o")
        if self.enabled and OpenAI and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            self.enabled = False

    def _extract_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def interpret_discovery(self, msg: str) -> Dict[str, Optional[str]]:
        if not self.enabled or not self.client:
            return {"region": None, "context": None, "timing": None, "constraints": None, "confidence": "low"}
        safe_msg = redact_phi(msg or "")
        system = (
            "You extract structured fields from a user reply in a lymphatic wellness chat. "
            "Return JSON only, no extra text. "
            "Allowed values: "
            "region = legs, arms, neck, core, general, unknown. "
            "context = post_op, travel, heat, workout, pregnancy, daily, unknown. "
            "timing = morning, afternoon, evening, all_day, variable, unknown. "
            "confidence = low, medium, high. "
            "If unclear, set unknown and confidence low. "
            "If the user mentions limitations like time, pain, mobility, schedule, equipment, add constraints as a short string."
        )
        user = (
            "User reply: " + safe_msg + "\n\n" +
            "Return JSON with keys: region, context, timing, constraints, confidence."
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user}]},
                ],
                temperature=0,
                max_output_tokens=200,
            )
            content = response.output_text if response and getattr(response, "output_text", None) else ""
            parsed = self._extract_json(content)
            if not parsed:
                return {"region": None, "context": None, "timing": None, "constraints": None, "confidence": "low"}
            return {
                "region": parsed.get("region"),
                "context": parsed.get("context"),
                "timing": parsed.get("timing"),
                "constraints": parsed.get("constraints"),
                "confidence": parsed.get("confidence", "low"),
            }
        except Exception:
            return {"region": None, "context": None, "timing": None, "constraints": None, "confidence": "low"}

    def interpret_agreement(self, msg: str) -> Dict[str, Optional[str]]:
        if not self.enabled or not self.client:
            return {"decision": None, "constraints": None, "confidence": "low"}
        safe_msg = redact_phi(msg or "")
        system = (
            "You classify a user reply to a proposed wellness routine. "
            "Return JSON only. "
            "decision values: agree, modify, question, decline, unsure. "
            "constraints: short phrase if the user mentions limitations. "
            "confidence: low, medium, high."
        )
        user = (
            "User reply: " + safe_msg + "\n\n" +
            "Return JSON with keys: decision, constraints, confidence."
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user}]},
                ],
                temperature=0,
                max_output_tokens=120,
            )
            content = response.output_text if response and getattr(response, "output_text", None) else ""
            parsed = self._extract_json(content)
            if not parsed:
                return {"decision": None, "constraints": None, "confidence": "low"}
            return {
                "decision": parsed.get("decision"),
                "constraints": parsed.get("constraints"),
                "confidence": parsed.get("confidence", "low"),
            }
        except Exception:
            return {"decision": None, "constraints": None, "confidence": "low"}
