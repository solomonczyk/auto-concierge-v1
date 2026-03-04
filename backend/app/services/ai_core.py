import json
import logging
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.services.ai_service import ai_service
from app.models.models import Service, AppointmentStatus

logger = logging.getLogger(__name__)

class DiagnosticResult(BaseModel):
    category: str = Field(description="Strict category of repair")
    urgency: str = Field(description="Низкая|Средняя|Высокая")
    estimated_hours: float = Field(description="Estimated time to complete the work")
    confidence: float = Field(description="Confidence score between 0 and 1")
    summary: str = Field(description="A very brief technical summary of the identified issue in Russian")
    clarifying_question: str = Field(description="A question to clarify symptoms in Russian")
    recommended_service: Optional[str] = Field(
        default=None,
        description="EXACT name of the single most appropriate service from the provided list"
    )

class AICore:
    """
    AI Core: 1-2 focused LLM calls to diagnose and recommend a single service.
    """

    async def classify_and_diagnose(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        db_services: Optional[List[Service]] = None
    ) -> Optional[DiagnosticResult]:
        """
        DiagnosticClassifier: 1 LLM call.
        Analyzes the problem and selects ONE service from the real catalog.
        """
        # Build service list for the prompt
        services_block = ""
        if db_services:
            names = [s.name for s in db_services]
            services_block = (
                "\n\nAVAILABLE SERVICES (choose EXACTLY one name from this list for recommended_service):\n"
                + "\n".join(f"- {n}" for n in names)
            )

        system_prompt = f"""You are a Diagnostic Classifier for a car service center.
Analyze the user's car problem and output a STRICT JSON object.

Output format:
{{
    "category": "Двигатель|Ходовая|Тормозная система|Электрика|Кузов|ТО|Другое",
    "urgency": "Низкая|Средняя|Высокая",
    "estimated_hours": float,
    "confidence": float,
    "summary": "Краткое техническое описание проблемы на РУССКОМ ЯЗЫКЕ",
    "clarifying_question": "Уточняющий вопрос на РУССКОМ ЯЗЫКЕ",
    "recommended_service": "EXACT service name from the list below, or null"
}}

CATEGORY RULES (follow strictly):
- "Электрика" — стеклоочистители, дворники, омыватели, фары, лампы, аккумулятор, стартер, генератор, предохранители, электроокна, сигнализация, не заводится
- "Двигатель" — троит, дымит, глохнет, потеря мощности, стук в двигателе, перегрев
- "Ходовая" — стуки снизу, вибрация, увод в сторону, подвеска, рулевое
- "Тормозная система" — плохо тормозит, скрип тормозов, колодки, диски, тормозная жидкость
- "Кузов" — ТОЛЬКО вмятины, царапины, покраска, ржавчина, рихтовка
- "ТО" — плановое ТО, замена масла/фильтров/жидкостей
{services_block}

RULES FOR recommended_service:
- Pick the SINGLE most relevant service for THIS specific problem
- Use the EXACT name from the list above (copy-paste)
- If no service fits at all, use null
- NEVER invent service names not in the list

IMPORTANT: All Russian text fields must be in Russian. No chatter. ONLY JSON.
If user is just greeting or asking something completely unrelated to cars — return category "Другое" and confidence 0."""

        try:
            response_text = await ai_service.get_chat_response(
                system_prompt=system_prompt,
                user_message=user_message,
                history=history
            )

            cleaned_json = response_text.strip()

            if "{" not in cleaned_json or "}" not in cleaned_json:
                logger.warning(f"AI returned non-JSON response: {cleaned_json}")
                return None

            start_idx = cleaned_json.find('{')
            end_idx = cleaned_json.rfind('}')
            cleaned_json = cleaned_json[start_idx:end_idx+1]
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

    def planner(
        self,
        diagnosis: Optional[DiagnosticResult],
        db_services: List[Service],
        context_text: str = ""
    ) -> List[Service]:
        """
        Selects ONE best service.
        Priority: AI recommendation → category map → general fallback.
        """
        # 1. AI picked a specific service by exact name (highest priority)
        if diagnosis and diagnosis.recommended_service:
            rec_name = diagnosis.recommended_service.strip().lower()
            for service in db_services:
                if service.name.strip().lower() == rec_name:
                    return [service]
            # Soft match: recommended name is a substring of a real service name
            for service in db_services:
                if rec_name in service.name.lower() or service.name.lower() in rec_name:
                    return [service]

        # 2. Category-based fallback: one primary service per category
        if diagnosis:
            diag_cat = diagnosis.category.lower()
            ctx_lower = (context_text or "").lower()

            # ГРМ/ремень → general diagnostics
            if "двигатель" in diag_cat and any(kw in ctx_lower for kw in ["грм", "ремн", "ремень", "распред"]):
                for service in db_services:
                    if "диагностика автомобиля" in service.name.lower():
                        return [service]

            cat_map = {
                "электрика": ["электрооборудования"],
                "ходовая": ["ходовой"],
                "тормозная система": ["тормозных", "колодок"],
                "двигатель": ["компьютерная диагностика", "двигателя"],
                "то": ["масла", "фильтра"],
                "кузов": ["кузов"],
            }

            search_terms = cat_map.get(diag_cat, [diag_cat])
            candidates = [s for s in db_services if any(t in s.name.lower() for t in search_terms)]
            if candidates:
                # Return the most specific match (longest name)
                candidates.sort(key=lambda s: len(s.name), reverse=True)
                return [candidates[0]]

        # 3. Keyword fallback from context text
        if context_text:
            text_lower = context_text.lower()
            text_words = re.findall(r'\b\w{3,}\b', text_lower)

            car_stems = {
                "очист": "электрооборудования",
                "дворн": "электрооборудования",
                "омыв": "электрооборудования",
                "форсун": "электрооборудования",
                "элект": "электрооборудования",
                "свет": "электрооборудования",
                "ламп": "электрооборудования",
                "завод": "электрооборудования",
                "аккум": "электрооборудования",
                "генер": "электрооборудования",
                "старт": "электрооборудования",
                "ходо": "ходовой",
                "подв": "ходовой",
                "стуч": "ходовой",
                "торм": "тормозных",
                "двиг": "двигателя",
                "тяга": "компьютерная",
                "мощн": "компьютерная",
                "трои": "двигателя",
                "глох": "двигателя",
                "дым": "двигателя",
                "грм": "диагностика автомобиля",
                "ремн": "диагностика автомобиля",
                "чек": "компьютерная",
                "масл": "масла",
                "вмят": "кузов",
                "покрас": "кузов",
                "царап": "кузов",
                "рихт": "кузов",
                "шины": "шиномонтаж",
            }

            for stem, match_term in car_stems.items():
                if any(word.startswith(stem) for word in text_words):
                    candidates = [s for s in db_services if match_term in s.name.lower()]
                    if candidates:
                        candidates.sort(key=lambda s: len(s.name), reverse=True)
                        return [candidates[0]]

        # 4. Final fallback: "Диагностика автомобиля" or any diagnostics
        for service in db_services:
            if "диагностика автомобиля" == service.name.lower():
                return [service]
        for service in db_services:
            if "компьютерная диагностика" in service.name.lower():
                return [service]
        for service in db_services:
            if "диагностика" in service.name.lower():
                return [service]

        return []

ai_core = AICore()
