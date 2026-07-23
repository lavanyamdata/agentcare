import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict
from app.database.session import get_db
from app.database.models import AuditEvent

logger = logging.getLogger("agentcare.audit")


def log_event(action, actor_id=None, entity_type=None, entity_id=None, metadata=None):
    try:
        with get_db() as db:
            event = AuditEvent(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                event_metadata=json.dumps(metadata or {}),
                created_at=datetime.utcnow(),
            )
            db.add(event)
            db.flush()
            event_id = event.id
            logger.info("AUDIT action=" + action)
            return event_id
    except Exception as e:
        logger.error("Audit log FAILED: " + str(e))
        return -1


def get_audit_log(entity_type=None, entity_id=None, actor_id=None, limit=100):
    with get_db() as db:
        query = db.query(AuditEvent)
        if entity_type:
            query = query.filter(AuditEvent.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditEvent.entity_id == entity_id)
        if actor_id:
            query = query.filter(AuditEvent.actor_id == actor_id)
        events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "action": e.action,
                "actor_id": e.actor_id,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "metadata": json.loads(e.event_metadata or "{}"),
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for e in events
        ]
