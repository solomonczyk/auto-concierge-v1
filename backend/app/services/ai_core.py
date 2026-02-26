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
        
        # 2. Match by keywords in context_text (Aggressive matching)
        if not matched_services and context_text:
            text_lower = context_text.lower()
            import re
            text_words = re.findall(r'\b\w{3,}\b', text_lower)
            
            # Common car stems mapping to categories or general services
            car_stems = {
                "диаг": "диагностика",
                "свет": "электрооборудования",
                "ламп": "электрооборудования",
                "элект": "электрооборудования",
                "ходо": "ходовой",
                "подв": "ходовой",
                "стуч": "ходовой",
                "торм": "тормозных",
                "двиг": "компьютерная",
                "масл": "масла",
                "фильт": "фильтра"
            }

            for service in db_services:
                svc_name = service.name.lower()
                # Check if any car stem in text matches this service
                for stem, match_term in car_stems.items():
                    if any(word.startswith(stem) for word in text_words) and match_term in svc_name:
                        matched_services.append(service)
                        break
                
                if service in matched_services:
                    continue

                # Normal word-based matching
                name_words = [k.strip().lower() for k in service.name.split() if len(k) >= 3]
                matched_this = False
                for skw in name_words:
                    skw_stem = skw[:4]
                    for word in text_words:
                        if word.startswith(skw_stem) or skw_stem.startswith(word[:4]):
                            matched_services.append(service)
                            matched_this = True
                            break
                    if matched_this:
                        break
        
        # 3. Final Fallback: if we found nothing but there's a problem, suggest general diagnostics
        if not matched_services and any(kw in context_text.lower() for kw in ["проблем", "сломал", "нужн", "помощ", "диагност"]):
            for service in db_services:
                if "компьютерная диагностика" in service.name.lower():
                    matched_services.append(service)
                    break
            if not matched_services: # If not found, any diagnostics
                for service in db_services:
                    if "диагностика" in service.name.lower():
                        matched_services.append(service)
                        break
                    
        return matched_services

ai_core = AICore()
