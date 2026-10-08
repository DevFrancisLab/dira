from .models import AuditEvent

USER_CREATED = "user_created"
USER_DEACTIVATED = "user_deactivated"
USER_REACTIVATED = "user_reactivated"
LOGIN_SUCCEEDED = "login_succeeded"
LOGIN_FAILED = "login_failed"


def record(action, subject_email="", actor=None):
    AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        subject_email=(subject_email or "")[:254],
    )
