import json
import os
import re
from typing import Optional, Dict

from services.redaction import redact_phi

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class ResponseInterpreter:
    """
    Lightweight semantic parser for discovery answers.
    Uses a low cost model to return structured slots and confidence.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = os.getenv("LLM_INTERPRETER_ENABLED", "true").lower() == "true"
        self.model = os.getenv("LLM_INTERPRETER_MODEL", "gpt-4o-mini")
        if self.enabled and OpenAI and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            self.enabled = False

    def _build_prompt(self, msg: str) -> Dict[str, str]:
        system = (
            "You extract structured fields from a user reply in a lymphatic wellness chat. "
            "Return JSON only. Do not add extra text. "
            "Allowed values: "
            "region = legs, arms, neck, core, general, unknown. "
            "context = post_op, travel, heat, workout, pregnancy, daily, unknown. "
            "timing = morning, afternoon, evening, all_day, variable, unknown. "
            "severity = mild, moderate, severe, unknown. "
            "confidence = low, medium, high. "
            "If unclear, set unknown and confidence low. "
            "Include constraints as a short string if user mentions limits like time, pain, mobility, schedule, equipment."
        )
        user = (
            "User reply: " + msg + "\n\n" +
            "Return JSON with keys: region, context, timing, severity, constraints, confidence."
        )
        return {"system": system, "user": user}

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

    def interpret(self, msg: str) -> Dict[str, Optional[str]]:
        if not self.enabled or not self.client:
            return {"region": None, "context": None, "timing": None, "severity": None, "constraints": None, "confidence": "low"}
        safe_msg = redact_phi(msg or "")
        prompts = self._build_prompt(safe_msg)
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": prompts["system"]}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompts["user"]}]},
                ],
                temperature=0,
                max_output_tokens=200,
            )
            content = response.output_text if response and getattr(response, "output_text", None) else ""
            parsed = self._extract_json(content)
            if not parsed:
                return {"region": None, "context": None, "timing": None, "severity": None, "constraints": None, "confidence": "low"}
            return {
                "region": parsed.get("region"),
                "context": parsed.get("context"),
                "timing": parsed.get("timing"),
                "severity": parsed.get("severity"),
                "constraints": parsed.get("constraints"),
                "confidence": parsed.get("confidence", "low"),
            }
        except Exception:
            return {"region": None, "context": None, "timing": None, "severity": None, "constraints": None, "confidence": "low"}
