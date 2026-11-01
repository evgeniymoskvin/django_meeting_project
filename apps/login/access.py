from apps.login.models import UserIdentity
from apps.legacy_models.models import EmployeeModel


def get_allowed_user(subject):
    identity = (
        UserIdentity.objects
        .select_related("user")
        .filter(subject=subject)
        .first()
    )

    if not identity:
        return None

    user = identity.user

    if not user.is_active:
        return None

    employee_exists = EmployeeModel.objects.filter(
        user_id=user.pk,
        work_status=True,
    ).exists()

    if not employee_exists:
        return None

    return user