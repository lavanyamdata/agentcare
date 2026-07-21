"""
seed.py — Populates database with synthetic test data.
Run once to create demo users, departments, doctors and slots.
All data is completely fictional — no real patient data.

NOTE — HARDCODED PASSWORDS:
Passwords are hardcoded for demo purposes only.
All patients use: Patient@123
All staff use:    Staff@123
Passwords are bcrypt hashed before storing — never plain text in DB.

FUTURE ENHANCEMENT:
Replace hardcoded passwords with a self-registration flow where
users set their own password via a registration form.
See FUTURE_ENHANCEMENTS.md for full details.
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
    """
    Convert plain text password to bcrypt hash.
    One-way hash — cannot be reversed back to plain text.
    Salt is generated randomly and embedded in the hash string.
    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def seed_all() -> None:
    """
    Create all tables then insert synthetic demo data.
    Safe to call multiple times — skips if data already exists.
    """

    # Step 1: Create all 11 tables first
    # Tables must exist before we can INSERT into them
    init_db()

    with get_db() as db:

        # Skip if already seeded
        # Equivalent to: IF EXISTS (SELECT 1 FROM users) RETURN
        if db.query(User).count() > 0:
            logger.info("Already seeded — skipping.")
            return

        logger.info("Seeding database...")

        # ── Staff users ──────────────────────────────────────────────
        # INSERT INTO users (name, email, password_hash, role) VALUES (...)
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
        db.flush()  # get IDs without committing

        # ── Patient users + profiles ─────────────────────────────────
        # Each patient needs two inserts:
        # 1. INSERT INTO users
        # 2. INSERT INTO patient_profiles (with FK to users.id)
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
            db.flush()  # need user.id for profile FK

            # Insert into patient_profiles table
            # user_id is FK → users.id
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
        # INSERT INTO departments (name, description, active)
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
        # Each doctor has FK → departments.id
        doctors_data = [
            ("Dr. Arjun Mehta",   "Cardiology"),
            ("Dr. Sunita Rao",    "Cardiology"),
            ("Dr. David Okafor",  "Neurology"),
            ("Dr. Priya Nair",    "Neurology"),
            ("Dr. Carlos Rivera", "Orthopedics"),
            ("Dr. Emily Zhang",   "Orthopedics"),
        ]

        # Build lookup dictionary: dept name → dept object
        # Avoids extra SELECT queries for each doctor
        # Equivalent to: SELECT id FROM departments WHERE name = @dept_name
        dept_map = {d.name: d for d in departments}

        doctors = []
        for name, dept_name in doctors_data:
            doc = Doctor(
                name=name,
                department_id=dept_map[dept_name].id,
                active=True
            )
            db.add(doc)
            doctors.append(doc)  # save for slot creation below
        db.flush()

        # ── Appointment slots (5 per doctor, next 14 days) ───────────
        # Each slot has FK → doctors.id
        # Spread across different days and times

        # Today at midnight UTC
        # Equivalent to: CAST(GETUTCDATE() AS DATE)
        base_date = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Available appointment hours
        slot_hours = [9, 10, 11, 14, 15]  # 9am, 10am, 11am, 2pm, 3pm
        slots_created = 0

        # Two nested loops = CROSS JOIN between doctors and hours
        for day_offset, doc in enumerate(doctors):
            for i, hour in enumerate(slot_hours):

                # Spread slots across different days
                # Equivalent to: DATEADD(day, ..., @base_date)
                slot_day = base_date + timedelta(
                    days=(day_offset * 2 + i % 3 + 1)
                )

                # Set the hour on the date
                # Equivalent to: DATEADD(hour, @hour, @slot_day)
                start = slot_day.replace(hour=hour)

                # Add 30 minutes for end time
                # Equivalent to: DATEADD(minute, 30, @start)
                end = start + timedelta(minutes=30)

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

    # Prints after the with block commits everything
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