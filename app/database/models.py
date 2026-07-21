"""
models.py — Database schema for AgentCare.
All 11 tables defined as SQLAlchemy ORM models.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Login identity. Role = patient or staff."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(120), nullable=False)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(SAEnum("patient", "staff", name="user_role"), nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient_profile = relationship("PatientProfile", back_populates="user", uselist=False)
    audit_events    = relationship("AuditEvent", back_populates="actor")


class PatientProfile(Base):
    """Extended patient details. Linked 1:1 to a patient User."""
    __tablename__ = "patient_profiles"

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    date_of_birth     = Column(String(10))
    phone             = Column(String(20))
    preferred_language = Column(String(50), default="English")
    emergency_contact = Column(String(120))
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user         = relationship("User", back_populates="patient_profile")
    appointments = relationship("Appointment", back_populates="patient")
    documents    = relationship("PatientDocument", back_populates="patient")
    workflow_runs = relationship("WorkflowRun", back_populates="patient")
    reminders    = relationship("Reminder", back_populates="patient")


class Department(Base):
    """Hospital departments. Routing Agent maps requests to these."""
    __tablename__ = "departments"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    active      = Column(Boolean, default=True, nullable=False)

    doctors = relationship("Doctor", back_populates="department")


class Doctor(Base):
    """Doctors belong to one department."""
    __tablename__ = "doctors"

    id            = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    name          = Column(String(120), nullable=False)
    active        = Column(Boolean, default=True, nullable=False)

    department   = relationship("Department", back_populates="doctors")
    slots        = relationship("AppointmentSlot", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class AppointmentSlot(Base):
    """Available time windows per doctor.
    Status: available → booked → available (if cancelled)"""
    __tablename__ = "appointment_slots"

    id         = Column(Integer, primary_key=True, index=True)
    doctor_id  = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time   = Column(DateTime, nullable=False)
    status     = Column(
        SAEnum("available", "booked", "blocked", name="slot_status"),
        default="available", nullable=False
    )

    doctor      = relationship("Doctor", back_populates="slots")
    appointment = relationship("Appointment", back_populates="slot", uselist=False)


class Appointment(Base):
    """Patient-doctor bookings.
    Status: pending → confirmed → completed | cancelled | rescheduled"""
    __tablename__ = "appointments"

    id         = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patient_profiles.id"), nullable=False)
    doctor_id  = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slot_id    = Column(Integer, ForeignKey("appointment_slots.id"), nullable=False)
    status     = Column(
        SAEnum("pending", "confirmed", "completed", "cancelled", "rescheduled",
               name="appt_status"),
        default="pending", nullable=False
    )
    reason     = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient   = relationship("PatientProfile", back_populates="appointments")
    doctor    = relationship("Doctor", back_populates="appointments")
    slot      = relationship("AppointmentSlot", back_populates="appointment")
    reminders = relationship("Reminder", back_populates="appointment")


class PatientDocument(Base):
    """Uploaded medical documents.
    Checksum used for duplicate detection."""
    __tablename__ = "patient_documents"

    id                = Column(Integer, primary_key=True, index=True)
    patient_id        = Column(Integer, ForeignKey("patient_profiles.id"), nullable=False)
    document_type     = Column(String(50), nullable=False)
    file_path         = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    document_date     = Column(String(10))
    checksum          = Column(String(64), nullable=False)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient = relationship("PatientProfile", back_populates="documents")


class WorkflowRun(Base):
    """Tracks every agent workflow from start to finish.
    State column stores full AgentState as JSON."""
    __tablename__ = "workflow_runs"

    id           = Column(Integer, primary_key=True, index=True)
    patient_id   = Column(Integer, ForeignKey("patient_profiles.id"), nullable=False)
    raw_request  = Column(Text, nullable=False)
    current_step = Column(String(50))
    state        = Column(Text)
    status       = Column(
        SAEnum("running", "completed", "failed", "escalated", name="run_status"),
        default="running", nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient     = relationship("PatientProfile", back_populates="workflow_runs")
    escalations = relationship("Escalation", back_populates="workflow_run")


class Reminder(Base):
    """Appointment and follow-up reminders created by Follow-up Agent."""
    __tablename__ = "reminders"

    id             = Column(Integer, primary_key=True, index=True)
    patient_id     = Column(Integer, ForeignKey("patient_profiles.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    reminder_type  = Column(String(50), nullable=False)
    message        = Column(Text)
    scheduled_at   = Column(DateTime, nullable=False)
    status         = Column(
        SAEnum("pending", "sent", "dismissed", name="reminder_status"),
        default="pending", nullable=False
    )

    patient     = relationship("PatientProfile", back_populates="reminders")
    appointment = relationship("Appointment", back_populates="reminders")


class Escalation(Base):
    """Created by Safety Agent when request needs human review.
    Staff must approve or reject before workflow continues."""
    __tablename__ = "escalations"

    id              = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    reason          = Column(Text, nullable=False)
    status          = Column(
        SAEnum("pending", "approved", "rejected", name="escalation_status"),
        default="pending", nullable=False
    )
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    staff_notes = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow_run = relationship("WorkflowRun", back_populates="escalations")


class AuditEvent(Base):
    """Immutable log of every significant action.
    Never updated or deleted — append only."""
    __tablename__ = "audit_events"

    id             = Column(Integer, primary_key=True, index=True)
    actor_id       = Column(Integer, ForeignKey("users.id"), nullable=True)
    action         = Column(String(100), nullable=False)
    entity_type    = Column(String(50))
    entity_id      = Column(Integer)
    event_metadata = Column(Text)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)

    actor = relationship("User", back_populates="audit_events")