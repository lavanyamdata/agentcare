import logging
import functools
import bcrypt
from sqlalchemy.orm import make_transient
from app.database.session import get_db
from app.database.models import User, PatientProfile

logger = logging.getLogger("agentcare.rbac")


class AuthError(Exception):
    pass


class PermissionError(Exception):
    pass


def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def authenticate_user(email, password):
    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            logger.warning("Login failed: unknown email=" + email)
            return None
        if not verify_password(password, user.password_hash):
            logger.warning("Login failed: wrong password for email=" + email)
            return None
        db.expunge(user)
        make_transient(user)
        logger.info("Login success: user_id=" + str(user.id) + " role=" + user.role)
        return user


def require_role(*allowed_roles):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            actor_role = kwargs.get("actor_role")
            if actor_role is None:
                raise AuthError("actor_role is required.")
            if actor_role not in allowed_roles:
                logger.warning("Access denied: role=" + str(actor_role) +
                               " tried to call " + func.__name__)
                raise PermissionError("Role " + str(actor_role) +
                                      " not authorized for " + func.__name__)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def assert_patient_owns(patient_profile_id, actor_id, actor_role):
    if actor_role == "staff":
        return
    with get_db() as db:
        profile = db.query(PatientProfile).filter_by(
            id=patient_profile_id,
            user_id=actor_id
        ).first()
        if not profile:
            logger.warning("Ownership check failed: actor_id=" +
                           str(actor_id) + " tried to access profile_id=" +
                           str(patient_profile_id))
            raise PermissionError("Patient " + str(actor_id) +
                                  " does not own profile " +
                                  str(patient_profile_id))


def get_patient_profile_for_user(user_id):
    with get_db() as db:
        profile = db.query(PatientProfile).filter_by(user_id=user_id).first()
        if profile:
            db.expunge(profile)
            make_transient(profile)
        return profile
