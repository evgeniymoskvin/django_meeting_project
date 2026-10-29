from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View

from apps.legacy_models.models import EmployeeModel
from apps.meeting_core.models import (
    MeetingAccessModel,
    MeetingEmployeesModel,
    MeetingModel,
)
from apps.meeting_core.permissions import (
    get_current_employee,
    get_meeting_permissions,
)


# Create your views here.
@method_decorator(login_required, name="dispatch")
class MeetingAccessGrantView(View):
    """Выдача сотрудникам дополнительного доступа к совещанию."""

    def post(self, request, pk):
        meeting = get_object_or_404(MeetingModel, pk=pk)
        permissions = get_meeting_permissions(meeting, request.user)

        if not permissions["can_manage_access"]:
            return HttpResponseForbidden("Недостаточно прав.")

        employee_ids = set(request.POST.getlist("employee_ids"))
        if not employee_ids:
            messages.warning(request, "Выбери хотя бы одного сотрудника.")
            return redirect("meeting_frontend:meeting_detail", pk=meeting.pk)

        current_employee = get_current_employee(request.user)

        employees = EmployeeModel.objects.filter(pk__in=employee_ids)

        # Создателю и участникам дополнительные записи доступа не нужны.
        participant_ids = MeetingEmployeesModel.objects.filter(
            meeting=meeting
        ).values_list("employee_id", flat=True)

        employees = employees.exclude(pk=meeting.created_by_id)
        employees = employees.exclude(pk__in=participant_ids)

        permission_fields = (
            "can_play_audio",
            "can_download_audio",
            "can_view_transcript",
            "can_view_summary",
            "can_view_protocol",
            "can_edit_protocol",
            "can_manage_access",
        )

        granted_permissions = {
            field: request.POST.get(field) == "on"
            for field in permission_fields
        }

        if not any(granted_permissions.values()):
            messages.warning(
                request,
                "Выбери хотя бы одно право доступа.",
            )
            return redirect("meeting_frontend:meeting_detail", pk=meeting.pk)

        # Только создатель совещания может выдавать право управления доступом.
        is_owner = meeting.created_by_id == getattr(
            current_employee, "pk", None
        )
        if not is_owner:
            granted_permissions["can_manage_access"] = False

        with transaction.atomic():
            for employee in employees:
                MeetingAccessModel.objects.update_or_create(
                    meeting=meeting,
                    employee=employee,
                    defaults={
                        **granted_permissions,
                        "granted_by": current_employee,
                    },
                )

        messages.success(request, "Права доступа обновлены.")
        return redirect("meeting_frontend:meeting_detail", pk=meeting.pk)


@method_decorator(login_required, name="dispatch")
class MeetingAccessRevokeView(View):
    """Отзыв дополнительного доступа у сотрудника."""

    def post(self, request, pk, access_id):
        meeting = get_object_or_404(MeetingModel, pk=pk)
        permissions = get_meeting_permissions(meeting, request.user)

        if not permissions["can_manage_access"]:
            return HttpResponseForbidden("Недостаточно прав.")

        grant = get_object_or_404(
            MeetingAccessModel,
            pk=access_id,
            meeting=meeting,
        )

        grant.delete()
        messages.success(request, "Дополнительный доступ отозван.")

        return redirect("meeting_frontend:meeting_detail", pk=meeting.pk)


class MeetingParticipantsAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        meeting = get_object_or_404(MeetingModel, pk=pk)

        employee = EmployeeModel.objects.filter(
            user=request.user
        ).first()

        # Добавлять участников может только создатель совещания.
        if employee is None or meeting.created_by_id != employee.pk:
            messages.error(
                request,
                "Добавлять участников может только создатель совещания."
            )
            return redirect("meeting_detail", pk=meeting.pk)

        participant_ids = request.POST.getlist("participant_ids")

        if not participant_ids:
            messages.warning(request, "Выберите хотя бы одного сотрудника.")
            return redirect("meeting_detail", pk=meeting.pk)

        # Не добавляем повторно существующих участников
        # и не добавляем создателя как отдельного участника.
        existing_ids = MeetingEmployeesModel.objects.filter(
            meeting=meeting
        ).values_list("employee_id", flat=True)

        eligible_employees = EmployeeModel.objects.exclude(
            pk=meeting.created_by_id
        ).exclude(
            pk__in=existing_ids
        )

        selected_employees = eligible_employees.filter(
            pk__in=participant_ids
        )

        added_count = 0

        for selected_employee in selected_employees:
            _, created = MeetingEmployeesModel.objects.get_or_create(
                meeting=meeting,
                employee=selected_employee,
            )
            if created:
                added_count += 1

        if added_count:
            messages.success(
                request,
                f"Добавлено участников: {added_count}."
            )
        else:
            messages.info(
                request,
                "Новых участников не добавлено."
            )

        return redirect("meeting_frontend:meeting_detail", pk=meeting.pk)


@method_decorator(login_required, name="dispatch")
class MeetingRenameView(View):
    def post(self, request, pk):
        meeting = get_object_or_404(MeetingModel, pk=pk)

        employee = get_current_employee(request.user)

        # Переименовывать совещание может только его создатель.
        if employee is None or meeting.created_by_id != employee.pk:
            return HttpResponseForbidden(
                "Изменять название может только создатель совещания."
            )

        new_title = request.POST.get("title", "").strip()

        if not new_title:
            messages.error(request, "Название совещания не может быть пустым.")
            return redirect(
                "meeting_frontend:meeting_detail",
                pk=meeting.pk,
            )

        if len(new_title) > 200:
            messages.error(
                request,
                "Название не должно превышать 200 символов.",
            )
            return redirect(
                "meeting_frontend:meeting_detail",
                pk=meeting.pk,
            )

        meeting.title = new_title
        meeting.save(update_fields=["title"])

        messages.success(request, "Название совещания успешно изменено.")

        return redirect(
            "meeting_frontend:meeting_detail",
            pk=meeting.pk,
        )
