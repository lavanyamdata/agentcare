from datetime import datetime, timedelta
from app.database.session import get_db
from app.database.models import Doctor, AppointmentSlot

with get_db() as db:
    doctors = db.query(Doctor).all()
    count = 0
    base = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    for doc in doctors:
        for day in range(1, 41):            # tomorrow through +40 days
            day_start = base + timedelta(days=day)
            if day_start.weekday() >= 5:    # skip weekends
                continue
            for hour_offset in [0, 2, 5]:   # 9:00, 11:00, 14:00
                start = day_start + timedelta(hours=hour_offset)
                exists = db.query(AppointmentSlot).filter(
                    AppointmentSlot.doctor_id == doc.id,
                    AppointmentSlot.start_time == start,
                ).first()
                if not exists:
                    db.add(AppointmentSlot(
                        doctor_id=doc.id,
                        start_time=start,
                        end_time=start + timedelta(minutes=30),
                        status="available",
                    ))
                    count += 1
print(f"Added {count} slots")