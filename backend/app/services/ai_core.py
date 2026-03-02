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
    clarifying_question: str = Field(description="A question to clarify symptoms and confirm the diagnosis")

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
            "category": "Двигатель|Ходовая|Тормозная система|Электрика|Кузов|ТО|Другое",
            "urgency": "Низкая|Средняя|Высокая",
            "estimated_hours": float,
            "confidence": float,
            "summary": "Техническое описание проблемы на РУССКОМ ЯЗЫКЕ",
            "clarifying_question": "Уточняющий вопрос на РУССКОМ ЯЗЫКЕ"
        }
        
        IMPORTANT: All text fields ("summary", "clarifying_question") MUST be in Russian.
        IMPORTANT: Always analyze symptoms like smoke, noise, or leaks as car problems. 
        If the user is just saying hello or asking a completely unrelated general question (not about cars), return category "Другое" and confidence 0.
        No conversational chatter. ONLY JSON.
        """
        
        # We reuse the existing AIService's GigaChat client if available, 
        # but here we want a strict JSON response.
        # For the purpose of this demo/implementation, we assume the underlying service 
        # can handle this strict prompt.
        
        try:
            # Use raw chat response for strict JSON output, passing history for context
            response_text = await ai_service.get_chat_response(
                system_prompt=system_prompt,
                user_message=user_message,
                history=history
            )
            
            # Robust JSON extraction
            cleaned_json = response_text.strip()
            
            # If the response doesn't look like JSON at all, it's probably an error message
            if "{" not in cleaned_json or "}" not in cleaned_json:
                logger.warning(f"AI returned non-JSON response: {cleaned_json}")
                return None

            # Find the first '{' and last '}'
            start_idx = cleaned_json.find('{')
            end_idx = cleaned_json.rfind('}')
            cleaned_json = cleaned_json[start_idx:end_idx+1]
            
            # Remove potential markdown formatting inside the extracted block
            cleaned_json = cleaned_json.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(cleaned_json)
                return DiagnosticResult(**data)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"Failed to parse JSON from AI: {e}. Content: {cleaned_json}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to classify diagnosis: {e}")
            return None

    def planner(self, diagnosis: Optional[DiagnosticResult], db_services: List[Service], context_text: str = "") -> List[Service]:
        """
        Pure business logic: Matches diagnostic category or text keywords to available services.
        """
        matched_services = []
        
        # 1. Strict name matching against context_text (Highest Priority)
        if context_text:
            context_lower = context_text.lower()
            for service in db_services:
                svc_name = service.name.lower()
                # If the specific service name is mentioned in the recommendation text
                if svc_name in context_lower:
                    # Give preference to specific diagnostics over general ones
                    matched_services.append(service)

            if matched_services:
                # Sort by name length descending to pick most specific one first
                # e.g., "Диагностика электрооборудования" > "Диагностика"
                matched_services.sort(key=lambda s: len(s.name), reverse=True)
                return matched_services

        # 2. Match by category from diagnosis (if high confidence)
        if diagnosis:
            diag_cat = diagnosis.category.lower()
            # Map Russian categories to search terms
            cat_map = {
                "электрика": ["электрооборудования", "диагностика"],
                "ходовая": ["ходовой", "диагностика"],
                "тормозная система": ["тормозных", "колодок"],
                "двигатель": ["компьютерная", "двигателя"],
                "то": ["масла", "фильтра"],
                "кузов": ["кузов"],
            }
            
            search_terms = cat_map.get(diag_cat, [diag_cat])
            
            for service in db_services:
                svc_name = service.name.lower()
                if any(term in svc_name for term in search_terms):
                    matched_services.append(service)
        
        # 3. Match by keywords in context_text (Aggressive matching)
        if not matched_services and context_text:
            text_lower = context_text.lower()
            import re
            text_words = re.findall(r'\b\w{3,}\b', text_lower)
            
            # Common car stems mapping to categories or general services
            car_stems = {
                "диаг": "диагностика",
                "элект": "электрооборудования",
                "свет": "электрооборудования",
                "ламп": "электрооборудования",
                "ходо": "ходовой",
                "подв": "ходовой",
                "стуч": "ходовой",
                "торм": "тормозных",
                "двиг": "двигателя",
                "тяга": "компьютерная", # "нету тяги" -> engine power
                "мощн": "компьютерная", # "потеря мощности"
                "трои": "двигателя", # "троит"
                "глох": "двигателя", # "глохнет"
                "дым": "двигателя", # "дымит"
                "чек": ["компьютерная", "диагностика"],
                "масл": ["масла", "фильтра"],
                "завод": ["электрооборудования"],
                "аккум": ["электрооборудования"],
                "вмят": ["кузов"],
                "покрас": ["кузов"],
                "царап": ["кузов"],
                "шины": ["шиномонтаж"]
            }

            for service in db_services:
                svc_name = service.name.lower()
                # Check if any car stem in text matches this service
                for stem, match_term in car_stems.items():
                    if any(word.startswith(stem) for word in text_words):
                        # Ensure match_term is a list for consistency
                        if isinstance(match_term, str):
                            match_term = [match_term]
                        if any(term in svc_name for term in match_term):
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
        
        # 3. Final Fallback: if we found nothing but there's a problem, suggest "Диагностика автомобиля"
        if not matched_services and any(kw in context_text.lower() for kw in ["проблем", "сломал", "диагност"]):
            # Try to find exactly "Диагностика автомобиля" first
            for service in db_services:
                if "диагностика автомобиля" == service.name.lower():
                    matched_services.append(service)
                    break
            
            # If not found, fall back to anything containing "компьютерная диагностика"
            if not matched_services:
                for service in db_services:
                    if "компьютерная диагностика" in service.name.lower():
                        matched_services.append(service)
                        break
            
            # Last resort: anything with "диагностика"
            if not matched_services:
                for service in db_services:
                    if "диагностика" in service.name.lower():
                        matched_services.append(service)
                        break
                    
        return matched_services

ai_core = AICore()
