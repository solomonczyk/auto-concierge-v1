"""
FSM states for Telegram bot conversation flows.
"""
from aiogram.fsm.state import State, StatesGroup


class ConsultForm(StatesGroup):
    """States for AI consultation dialog."""
    waiting_for_description = State()  # User describes the car problem
    waiting_for_followup = State()     # After AI response, waiting for next question or action
