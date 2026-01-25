import re

class SafetyService:
    """
    Electronic Guardrail Service for detecting medical emergencies and self-harm.
    Follows 'World Class' safety protocols for non-medical AI guides.
    """
    
    # Critical intents that trigger immediate hard-refusal
    EMERGENCY_KEYWORDS = [
        r"heart attack", r"chest pain", r"shortness of breath", 
        r"difficulty breathing", r"stroke", r"numb.* arm", r"arm.* numb",
        r"slurred speech", r"face drooping", r"emergency", r"911", r"ambulance"
    ]
    
    SELF_HARM_KEYWORDS = [
        r"kill myself", r"suicide", r"hurt myself", r"end it all"
    ]

    @staticmethod
    def check_emergency(text: str) -> str:
        """
        Scans text for emergency keywords. 
        Returns a hard-refusal message if an emergency is detected, else None.
        """
        text_lower = text.lower()
        
        # 1. Check for Medical Emergencies
        combined_keywords = SafetyService.EMERGENCY_KEYWORDS + SafetyService.SELF_HARM_KEYWORDS
        for pattern in combined_keywords:
            if re.search(pattern, text_lower):
                if pattern in SafetyService.EMERGENCY_KEYWORDS:
                    return ("I am an AI Wellness Guide, not a doctor. Based on what you're describing, "
                            "**please call local emergency services (like 911) or go to the nearest emergency room immediately.** "
                            "Your safety is the priority, and these symptoms require urgent medical evaluation.")
                else:
                    return ("I'm strictly an AI Wellness Guide, but I want to make sure you're safe. "
                            "If you're feeling overwhelmed, please reach out to a crisis hotline or a mental health professional. "
                            "You can call or text **988** in the US/Canada, or reach out to local emergency services for immediate support.")

        return None
