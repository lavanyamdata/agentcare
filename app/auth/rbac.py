import logging
import bcrypt
from sqlalchemy.orm import make_transient
from app.database.session import get_db
from app.database.models import User, PatientProfile

logger = logging.getLogger("agentcare.rbac")


class AuthError(Exception):
    pass


class PermissionError(Exception):
    pass


def check_role(actor_role, allowed_roles, function_name):
    """
    Simple role check. Call at top of any protected function.
    
    actor_role:    role of person calling the function
    allowed_roles: list of roles that are allowed
    function_name: name of function being protected (for error message)
    
    Example:
        def approve_escalation(actor_role, actor_id):
            check_role(actor_role, ["staff"], "approve_escalation")
            # actual work here
    """
    if actor_role not in allowed_roles:
        logger.warning(
            "Access denied: role=" + str(actor_role) +
            " tried to call " + function_name
        )
        raise PermissionError(
            function_name + " requires role: " + str(allowed_roles) +
            " but got: " + str(actor_role)
        )


def verify_password(plain, hashed):
    """
    Check plain text password against stored bcrypt hash.
    Returns True if match, False if not.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def authenticate_user(email, password):
    """
    Verify login credentials.
    Returns User object if valid, None if invalid.
    """
    with get_db() as db:
        user = db.query(User).filter_by(email=email).first()

        if not user:
            logger.warning("Login failed: unknown email=" + email)
            return None

        if not verify_password(password, user.password_hash):
            logger.warning("Login failed: wrong password for=" + email)
            return None

        # Detach from session so attributes work after session closes
        db.expunge(user)
        make_transient(user)

        logger.info("Login OK: user_id=" + str(user.id) + " role=" + user.role)
        return user


def assert_patient_owns(patient_profile_id, actor_id, actor_role):
    """
    Ensure patient can only access their own records.
    Staff can access any record.
    
    Raises PermissionError if patient tries to access someone elses data.
    """
    # Staff can see everything
    if actor_role == "staff":
        return

    # Patient must own this profile
    with get_db() as db:
        profile = db.query(PatientProfile).filter_by(
            id=patient_profile_id,
            user_id=actor_id
        ).first()

        if not profile:
            logger.warning(
                "Ownership check failed: actor_id=" + str(actor_id) +
                " tried to access profile_id=" + str(patient_profile_id)
            )
            raise PermissionError(
                "Patient " + str(actor_id) +
                " does not own profile " + str(patient_profile_id)
            )


def get_patient_profile_for_user(user_id):
    """
    Get PatientProfile for a given user_id.
    Used after login to get patient_profile_id for session.
    Returns None if not found.
    """
    with get_db() as db:
        profile = db.query(PatientProfile).filter_by(
            user_id=user_id
        ).first()

        if profile:
            db.expunge(profile)
            make_transient(profile)

        return profile
