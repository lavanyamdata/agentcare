# Future Enhancements

Items consciously deferred during the hackathon build, with rationale. Core scope was prioritized: a fully wired agent workflow with real safety boundaries beats a wide but shallow feature list.

## Priority 1 — User lifecycle
- **Self-registration & password reset.** Current demo uses seeded accounts with known passwords (documented limitation in seed.py).
- Production path: registration flow + signed reset tokens .
- UI Enhancements

## Priority 2 — Appointment management UI
- **Reschedule / cancel from the patient portal.** Service layer already supports cancellation and the appointment state machine (VALID_TRANSITIONS includes `rescheduled`); the UI surface was cut for time.
- **Staff slot management UI.** Slots are currently seeded via scripts (`seed.py`, `add_slots.py`); staff should be able to create/close slots in the dashboard.

## Priority 3 — Reminders & documents
- **Reminders surfaced as notifications.** Reminders are created and persisted (24h pre-appointment + 7-day follow-up) but only viewable in a table; no email/SMS dispatch.
- **Document Agent as a distinct LLM agent.** Document services exist (SHA-256 dedup, missing-doc checks per department) and are exposed as tools, but classification is not yet LLM-driven.

