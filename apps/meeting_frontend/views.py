import json
import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View

from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from apps.legacy_models.models import EmployeeModel
from apps.meeting_core.models import MeetingModel, MeetingEmployeesModel, MeetingProtocolModel


# Create your views here.
class NewRecordingView(View):
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

    @method_decorator(login_required(login_url='login'))
    def get(self, request, *args, **kwargs):
        """Отображение страницы записи."""
        employees = (EmployeeModel.objects
                     .filter(work_status=True)
                     .order_by('last_name', 'first_name', 'middle_name'))

        content = {'employees': employees,
                   "meeting_title": "Новое совещание",
                   "meeting_date": timezone.localdate(),
                   "meeting_time": "Офлайн-совещание",
                   }
        return render(
            request,
            "meeting_frontend/recording_page.html", content
        )

    def post(self, request, *args, **kwargs):
        """Сохраняет совещание, аудио, участников и черновик протокола."""

        print(request.POST)
        # a = 10/0

        audio = request.FILES.get("audio")

        if not audio:
            return JsonResponse({
                "success": False,
                "error": "Аудиофайл не передан.",
            }, status=400)

        if audio.size == 0:
            return JsonResponse({
                "success": False,
                "error": "Получен пустой аудиофайл.",
            }, status=400)

        if audio.size > self.MAX_FILE_SIZE:
            return JsonResponse({
                "success": False,
                "error": "Размер записи превышает 500 МБ.",
            }, status=413)

        allowed_types = {
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mp4": ".mp4",
            "audio/mpeg": ".mp3",
            "audio/mp4a-latm": ".m4a",
        }

        content_type = (audio.content_type or "").split(";")[0].lower()

        if content_type not in allowed_types:
            return JsonResponse({
                "success": False,
                "error": "Неподдерживаемый формат аудиофайла.",
            }, status=415)

        # Название совещания.
        title = request.POST.get("meeting_title", "").strip()

        if not title:
            title = "Новое совещание"

        if len(title) > 200:
            return JsonResponse({
                "success": False,
                "error": "Название совещания не должно превышать 200 символов.",
            }, status=400)

        # Длительность.
        try:
            duration_seconds = int(request.POST.get("duration_seconds", 0))
            if duration_seconds < 0:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({
                "success": False,
                "error": "Некорректная длительность записи.",
            }, status=400)

        # Получаем ID участников из JSON, отправленного браузером.
        participant_ids = request.POST.getlist("participant_ids")

        try:
            participant_ids = [int(pk) for pk in participant_ids]
        except (TypeError, ValueError):
            return JsonResponse({
                "success": False,
                "error": "Неправильный список участников",
            }, status=400)

        employees = EmployeeModel.objects.filter(
            pk__in=participant_ids,
            work_status=True,
        )

        # Проверяем, что все переданные ID соответствуют найденным сотрудникам
        if employees.count() != len(set(participant_ids)):
            return JsonResponse({
                "success": False,
                "error": "В списке есть несуществующие или неактивные сотрудники",
            }, status=400)

        # Проверяем, что все выбранные сотрудники существуют и активны.
        employees = list(
            EmployeeModel.objects.filter(
                pk__in=participant_ids,
                work_status=True,
            )
        )

        if len(employees) != len(participant_ids):
            return JsonResponse({
                "success": False,
                "error": "Один или несколько участников не найдены или неактивны.",
            }, status=400)

        # ВАЖНО: адаптируй получение EmployeeModel к своей системе авторизации.
        # Предполагается, что у EmployeeModel есть FK user -> request.user.
        if not request.user.is_authenticated:
            return JsonResponse({
                "success": False,
                "error": "Для сохранения совещания необходимо авторизоваться.",
            }, status=401)

        try:
            creator = EmployeeModel.objects.get(user=request.user)
        except EmployeeModel.DoesNotExist:
            return JsonResponse({
                "success": False,
                "error": "Для текущего пользователя не найден сотрудник.",
            }, status=403)

        saved_audio_path = None

        try:
            with transaction.atomic():
                meeting = MeetingModel(
                    title=title,
                    created_by=creator,
                    duration_seconds=duration_seconds,
                    status=MeetingModel.Status.SAVED,
                )

                # FileField использует upload_to из модели.
                filename = f"{uuid.uuid4().hex}{allowed_types[content_type]}"
                meeting.audio_file.save(filename, audio, save=False)
                saved_audio_path = meeting.audio_file.name

                meeting.save()

                # Создаём связи с участниками.
                MeetingEmployeesModel.objects.bulk_create([
                    MeetingEmployeesModel(
                        meeting=meeting,
                        employee=employee,
                    )
                    for employee in employees
                ])

                # Создаём пустой черновик протокола.
                MeetingProtocolModel.objects.create(
                    meeting=meeting,
                    title=f"Протокол: {meeting.title}",
                    status=MeetingProtocolModel.Status.DRAFT,
                )

        except Exception:
            print("Ошибка при сохранении совещания")

            # База откатится транзакцией, файл удаляем отдельно.
            if saved_audio_path:
                try:
                    default_storage.delete(saved_audio_path)
                except Exception:
                    print(
                        "Не удалось удалить аудиофайл после ошибки сохранения"
                    )

            return JsonResponse({
                "success": False,
                "error": "Не удалось сохранить совещание. Попробуйте ещё раз.",
            }, status=500)

        return JsonResponse({
            "success": True,
            "message": "Совещание успешно сохранено.",
            "meeting_id": str(meeting.pk),
            "meeting_title": meeting.title,
            "meeting_url": reverse(
                "meeting_frontend:meeting_detail",
                kwargs={"pk": meeting.pk},
            ),
            "file": meeting.audio_file.name.rsplit("/", 1)[-1],
            "audio_path": meeting.audio_file.name,
            "duration_seconds": meeting.duration_seconds,
            "size": audio.size,
            "participants_count": len(employees),
            "protocol_id": str(meeting.protocol_document.pk),
        }, status=201)


class MeetingDetailView(View):
    def get(self, request, pk):
        meeting = get_object_or_404(
            MeetingModel.objects.select_related("created_by"),
            pk=pk,
        )

        participants = (
            MeetingEmployeesModel.objects
            .filter(meeting=meeting)
            .select_related("employee")
            .order_by("employee_id")
        )

        # OneToOneField: у совещания может ещё не быть протокола.
        try:
            protocol = meeting.protocol_document
        except MeetingProtocolModel.DoesNotExist:
            protocol = None

        context = {
            "meeting": meeting,
            "participants": participants,
            "protocol": protocol,
        }

        return render(
            request,
            "meeting_frontend/meeting_details.html",
            context,
        )
