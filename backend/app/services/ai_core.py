import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.services.ai_service import ai_service
from app.models.models import Service, AppointmentStatus

logger = logging.getLogger(__name__)

class DiagnosticResult(BaseModel):
    category: str = Field(description="Strict category of repair (e.g., suspension, engine, brakes, maintenance)")
    urgency: str = Field(description="Low, Medium, High")
    estimated_hours: float = Field(description="Estimated time to complete the work")
    confidence: float = Field(description="Confidence score between 0 and 1")
    summary: str = Field(description="A very brief technical summary of the identified issue")

class AICore:
    """
    Simplified AI Core (formerly MAS).
    Reduces 5+ agent calls to 1-2 focused LLM calls.
    """

    async def classify_and_diagnose(self, user_message: str, history: List[Dict[str, str]]) -> Optional[DiagnosticResult]:
        """
        DiagnosticClassifier: Uses 1 LLM call to extract technical metadata.
        """
        system_prompt = """
        You are a Diagnostic Classifier for a car service.
        Your goal is to analyze the user's description of a car problem and output a STRICT JSON object.
        
        Output format:
        {
            "category": "string",
            "urgency": "Low|Medium|High",
            "estimated_hours": float,
            "confidence": float,
            "summary": "string"
        }
        
        Categories: maintenance, engine, suspension, brakes, electrical, body, other.
        If the user is just saying hello or asking a general question, return category "other" and confidence 0.
        No conversational chatter. ONLY JSON.
        """
        
        # We reuse the existing AIService's GigaChat client if available, 
        # but here we want a strict JSON response.
        # For the purpose of this demo/implementation, we assume the underlying service 
        # can handle this strict prompt.
        
        try:
            # Here we would normally call the LLM. 
            # For now, we integrate with ai_service.get_consultation logic but with a JSON twist.
            response_text = await ai_service.get_consultation(
                user_message=f"Analyze this and return JSON: {user_message}",
                services=[] # No services needed for pure classification
            )
            
            # Basic JSON extraction from response (often wrapped in backticks)
            cleaned_json = response_text.strip()
            if "```json" in cleaned_json:
                cleaned_json = cleaned_json.split("```json")[-1].split("```")[0].strip()
            elif "```" in cleaned_json:
                cleaned_json = cleaned_json.split("```")[-1].split("```")[0].strip()
            
            data = json.loads(cleaned_json)
            return DiagnosticResult(**data)
        except Exception as e:
            logger.error(f"Failed to classify diagnosis: {e}")
            return None

    def planner(self, diagnosis: Optional[DiagnosticResult], db_services: List[Service], context_text: str = "") -> List[Service]:
        """
        Pure business logic: Matches diagnostic category or text keywords to available services.
        """
        matched_services = []
        
        # 1. Match by category (if diagnosis is high confidence)
        if diagnosis:
            diag_cat = diagnosis.category.lower()
            for service in db_services:
                if diag_cat in service.name.lower() or diag_cat in (service.description or "").lower():
                    matched_services.append(service)
        
        # 2. Match by keywords in context_text if no category matches
        if not matched_services and context_text:
            text_lower = context_text.lower()
            for service in db_services:
                # Basic keyword matching (e.g. "масло" for "Замена масла")
                # Split service name into keywords
                keywords = [k.strip().lower() for k in service.name.split() if len(k) > 3]
                if any(kw in text_lower for kw in keywords):
                    matched_services.append(service)
        
        # 3. If no specific matches, suggest general diagnostics if appropriate
        if not matched_services and ("проблема" in context_text.lower() or "сломалось" in context_text.lower()):
            for service in db_services:
                if "диагностика" in service.name.lower():
                    matched_services.append(service)
                    
        return matched_services

ai_core = AICore()
