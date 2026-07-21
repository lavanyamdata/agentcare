"""
seed.py — Populates database with synthetic test data.
Run once to create demo users, departments, doctors and slots.
All data is completely fictional — no real patient data.
"""

import logging
from datetime import datetime, timedelta
import bcrypt

from app.database.session import init_db, get_db
from app.database.models import (
    User, PatientProfile, Department, Doctor, AppointmentSlot
)

logger = logging.getLogger("agentcare.seed")


def hash_password(plain: str) -> str:
    """Convert plain text password to bcrypt hash."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def seed_all() -> None:
    """Create all tables then insert synthetic data."""

    # Step 1: Create tables first
    init_db()

    with get_db() as db:

        # Skip if already seeded
        if db.query(User).count() > 0:
            logger.info("Already seeded — skipping.")
            return

        logger.info("Seeding database...")

        # ── Staff users ──────────────────────────────────────────────
        staff_users = [
            User(name="Admin Singh",
                 email="admin@agentcare.dev",
                 password_hash=hash_password("Staff@123"),
                 role="staff"),
            User(name="Nurse Patel",
                 email="nurse@agentcare.dev",
                 password_hash=hash_password("Staff@123"),
                 role="staff"),
        ]
        db.add_all(staff_users)
        db.flush()

        # ── Patient users + profiles ─────────────────────────────────
        patients = [
            dict(name="Ravi Kumar",
                 email="ravi@example.com",
                 dob="1978-03-15",
                 phone="555-0101",
                 emergency="Priya Kumar / 555-0102"),
            dict(name="Meena Sharma",
                 email="meena@example.com",
                 dob="1985-07-22",
                 phone="555-0201",
                 emergency="Raj Sharma / 555-0202"),
            dict(name="James Carter",
                 email="james@example.com",
                 dob="1965-11-30",
                 phone="555-0301",
                 emergency="Linda Carter / 555-0302"),
        ]

        for p in patients:
            # Insert into users table
            user = User(
                name=p["name"],
                email=p["email"],
                password_hash=hash_password("Patient@123"),
                role="patient"
            )
            db.add(user)
            db.flush()  # get user.id before next insert

            # Insert into patient_profiles table
            profile = PatientProfile(
                user_id=user.id,
                date_of_birth=p["dob"],
                phone=p["phone"],
                preferred_language="English",
                emergency_contact=p["emergency"],
            )
            db.add(profile)

        db.flush()

        # ── Departments ──────────────────────────────────────────────
        departments = [
            Department(
                name="Cardiology",
                description="Heart and cardiovascular conditions",
                active=True
            ),
            Department(
                name="Neurology",
                description="Brain, spine and nervous system disorders",
                active=True
            ),
            Department(
                name="Orthopedics",
                description="Bone, joint and musculoskeletal conditions",
                active=True
            ),
        ]
        db.add_all(departments)
        db.flush()

        # ── Doctors (2 per department) ───────────────────────────────
        doctors_data = [
            ("Dr. Arjun Mehta",   "Cardiology"),
            ("Dr. Sunita Rao",    "Cardiology"),
            ("Dr. David Okafor",  "Neurology"),
            ("Dr. Priya Nair",    "Neurology"),
            ("Dr. Carlos Rivera", "Orthopedics"),
            ("Dr. Emily Zhang",   "Orthopedics"),
        ]

        # Build lookup: department name → department object
        dept_map = {d.name: d for d in departments}

        doctors = []
        for name, dept_name in doctors_data:
            doc = Doctor(
                name=name,
                department_id=dept_map[dept_name].id,
                active=True
            )
            db.add(doc)
            doctors.append(doc)
        db.flush()

        # ── Appointment slots (5 per doctor, next 14 days) ───────────
        base_date = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        slot_hours = [9, 10, 11, 14, 15]
        slots_created = 0

        for day_offset, doc in enumerate(doctors):
            for i, hour in enumerate(slot_hours):
                slot_day = base_date + timedelta(
                    days=(day_offset * 2 + i % 3 + 1)
                )
                start = slot_day.replace(hour=hour)
                end   = start + timedelta(minutes=30)

                db.add(AppointmentSlot(
                    doctor_id=doc.id,
                    start_time=start,
                    end_time=end,
                    status="available"
                ))
                slots_created += 1

        logger.info(
            "Seeded: 2 staff, 3 patients, 3 depts, 6 doctors, %d slots",
            slots_created
        )

    # This prints after the with block commits
    print("")
    print("Seed complete.")
    print("─" * 40)
    print("LOGIN CREDENTIALS:")
    print("  Staff:   admin@agentcare.dev  / Staff@123")
    print("  Staff:   nurse@agentcare.dev  / Staff@123")
    print("  Patient: ravi@example.com     / Patient@123")
    print("  Patient: meena@example.com    / Patient@123")
    print("  Patient: james@example.com    / Patient@123")
    print("─" * 40)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    seed_all()