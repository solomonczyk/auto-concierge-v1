import asyncio
from app.services.ai_core import AICore
from app.db.session import SessionLocal

async def test_ai():
    ai = AICore()
    db = SessionLocal()
    try:
        # A vague problem that should trigger clarification
        problem = "Что-то стучит в подвеске при повороте"
        print(f"Testing problem: {problem}")
        
        result = await ai.analyze_problem(problem, db)
        print(f"AI Result:")
        print(f"Category: {result.category}")
        print(f"Urgency: {result.urgency}")
        print(f"Summary: {result.summary}")
        print(f"Clarifying Question: {result.clarifying_question}")
        print(f"Matched Services: {[s.name for s in result.matched_services]}")
        
        if result.clarifying_question:
            print("SUCCESS: Clarifying question generated!")
        else:
            print("FAILURE: No clarifying question found.")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_ai())
