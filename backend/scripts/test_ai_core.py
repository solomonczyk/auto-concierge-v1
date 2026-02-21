import asyncio
import logging
import json
from unittest.mock import AsyncMock
from app.services.ai_core import ai_core, DiagnosticResult
from app.services.ai_service import ai_service
from app.models.models import Service, AppointmentStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock the AI service
# classify_and_diagnose calls ai_service.get_consultation
ai_service.get_consultation = AsyncMock(return_value=json.dumps({
    "category": "suspension",
    "urgency": "medium",
    "estimated_hours": 2.0,
    "confidence": 0.9,
    "summary": "Suspension clunking noise"
}))

async def test_ai_core():
    # 1. Mock services
    services = [
        Service(id=1, name="Oil Change", base_price=1500, duration_minutes=30),
        Service(id=2, name="Suspension Diagnostics", base_price=800, duration_minutes=45, description="We fix clunking suspension noises")
    ]

    # 2. Test Case: Clear suspension issue
    user_message = "My car makes a loud clunking noise when I go over bumps. I think it is the suspension."
    logger.info(f"Testing diagnostic for: '{user_message}'")
    
    # Needs history argument
    result = await ai_core.classify_and_diagnose(user_message, history=[])
    
    logger.info(f"AI Result: {result}")
    
    if result and result.category:
        logger.info(f"SUCCESS: AI categorized the issue as '{result.category}'")
        
        # 3. Test Case: Planner logic
        matched = ai_core.planner(result, services)
        logger.info(f"Planner matched services: {[s.name for s in matched]}")
        
        if any(s.name == "Suspension Diagnostics" for s in matched):
            logger.info("SUCCESS: Planner correctly matched the service based on category/description.")
    else:
        logger.error("AI could not categorize.")

if __name__ == "__main__":
    asyncio.run(test_ai_core())
