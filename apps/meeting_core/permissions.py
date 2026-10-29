from apps.legacy_models.models import EmployeeModel
from apps.meeting_core.models import (
    MeetingAccessModel,
    MeetingEmployeesModel,
)


def get_current_employee(user):
    """Возвращает сотрудника для авторизованного пользователя."""
    if not user.is_authenticated:
        return None

    return EmployeeModel.objects.filter(user=user).first()


def get_meeting_permissions(meeting, user):
    """
    Возвращает права пользователя на совещание.

    Создатель: полный доступ.
    Участник: просмотр материалов и прослушивание.
    Смотритель: права из MeetingAccessModel.
    """
    denied = {
        "can_view": False,
        "can_play_audio": False,
        "can_download_audio": False,
        "can_view_transcript": False,
        "can_view_summary": False,
        "can_view_protocol": False,
        "can_edit_protocol": False,
        "can_manage_access": False,
        "can_rename_meeting": False,
    }

    employee = get_current_employee(user)

    if employee is None:
        return denied

    # Создатель имеет полный доступ.
    if meeting.created_by_id == employee.pk:
        return {key: True for key in denied}

    # Участник совещания получает базовые права.
    is_participant = MeetingEmployeesModel.objects.filter(
        meeting=meeting,
        employee=employee,
    ).exists()

    if is_participant:
        return {
            "can_view": True,
            "can_play_audio": True,
            "can_download_audio": True,
            "can_view_transcript": True,
            "can_view_summary": True,
            "can_view_protocol": True,
            "can_edit_protocol": False,
            "can_manage_access": True,
            "can_rename_meeting": False,
        }

    # Дополнительный смотритель.
    grant = MeetingAccessModel.objects.filter(
        meeting=meeting,
        employee=employee,
    ).first()

    if grant is None:
        return denied

    return {
        "can_view": True,
        "can_play_audio": grant.can_play_audio,
        "can_download_audio": grant.can_download_audio,
        "can_view_transcript": grant.can_view_transcript,
        "can_view_summary": grant.can_view_summary,
        "can_view_protocol": grant.can_view_protocol,
        "can_edit_protocol": grant.can_edit_protocol,
        "can_manage_access": grant.can_manage_access,
        "can_rename_meeting": False,
    }
