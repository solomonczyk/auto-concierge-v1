from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.session import Base

APPOINTMENT_INTAKE_ALLOWED_STATUSES = (
    "pending",
    "in_progress",
    "completed",
)


class AppointmentIntake(Base):
    __tablename__ = "appointment_intakes"

    id = Column(Integer, primary_key=True)

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    status = Column(String, nullable=False, default="pending")
    answers_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
