import datetime

from django.core.exceptions import ValidationError
from uuid import UUID
from uuid_utils import uuid7

from django.conf import settings
from django.db import models

# Create your models here.
from apps.legacy_models.models import EmployeeModel
from django.db.models import F, Q


def generate_uuid7():
    return UUID(str(uuid7()))


def meeting_audio_upload_to(instance, filename):
    # Не используем исходное имя файла от браузера.
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    allowed_extensions = {"webm", "ogg", "wav", "mp3", "mp4", "m4a"}
    if extension not in allowed_extensions:
        extension = "webm"

    return f"meetings/audio/{generate_uuid7()}.{extension}"


class BaseMeetingModel(models.Model):
    """Абстрактная базовая модель."""

    id = models.UUIDField(
        primary_key=True,
        default=generate_uuid7,
        editable=False,
    )

    created_at = models.DateTimeField(
        verbose_name="Дата создания",
        auto_now_add=True,
    )

    class Meta:
        abstract = True


class MeetingModel(BaseMeetingModel):
    class Status(models.TextChoices):
        CREATED = "created", "Создано"
        UPLOADING = "uploading", "Загрузка аудио"
        SAVED = "saved", "Аудио сохранено"
        TRANSCRIBING = "transcribing", "Расшифровка"
        SUMMARIZING = "summarizing", "Подготовка содержания"
        GENERATING_PROTOCOL = "generating_protocol", "Подготовка протокола"
        READY = "ready", "Готово"
        ERROR = "error", "Ошибка обработки"

    title = models.CharField(
        max_length=200,
        verbose_name="Название совещания",
    )

    created_by = models.ForeignKey(
        EmployeeModel,
        on_delete=models.PROTECT,
        related_name="created_meetings",
        verbose_name="Создатель",
    )

    duration_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name="Длительность, секунд",
    )

    audio_file = models.FileField(
        upload_to=meeting_audio_upload_to,
        blank=True,
        verbose_name="Аудиозапись",
    )

    transcription = models.TextField(
        blank=True,
        verbose_name="Полная расшифровка",
    )

    summary = models.TextField(
        blank=True,
        verbose_name="Краткое содержание",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
        verbose_name="Статус",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Совещание"
        verbose_name_plural = "Совещания"

    def __str__(self):
        return self.title


class MeetingEmployeesModel(BaseMeetingModel):
    meeting = models.ForeignKey(
        MeetingModel,
        on_delete=models.CASCADE,
        related_name="employees_links",
    )

    employee = models.ForeignKey(
        EmployeeModel,
        on_delete=models.PROTECT,
        related_name="meeting_links",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "employee"],
                name="unique_meeting_employee",
            ),
        ]
        verbose_name = "Участник совещания"
        verbose_name_plural = "Участники совещаний"

    def __str__(self):
        return f"{self.meeting} — {self.employee}"


class MeetingProtocolModel(BaseMeetingModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        GENERATED = "generated", "Сформирован"
        REVIEW = "review", "На согласовании"
        APPROVED = "approved", "Согласован"
        SIGNED = "signed", "Подписан"

    meeting = models.OneToOneField(
        "MeetingModel",
        on_delete=models.CASCADE,
        related_name="protocol_document",
        verbose_name="Совещание",
    )

    title = models.CharField(
        max_length=255,
        default="Протокол совещания",
        verbose_name="Название документа",
    )

    content = models.TextField(
        blank=True,
        verbose_name="Содержание протокола",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="Статус протокола",
    )

    document_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата протокола",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Протокол совещания"
        verbose_name_plural = "Протоколы совещаний"

    def __str__(self):
        return f"{self.title} — {self.meeting.title}"


class MeetingAccessModel(BaseMeetingModel):
    """Таблица, кому расширен доступ для просмотра того или иного совещания"""
    meeting = models.ForeignKey(
        MeetingModel,
        on_delete=models.CASCADE,
        related_name="access_grants",
    )
    employee = models.ForeignKey(
        EmployeeModel,
        on_delete=models.CASCADE,
        related_name="meeting_access_grants",
    )

    can_play_audio = models.BooleanField(verbose_name="Может прослушивать аудио", default=True)
    can_download_audio = models.BooleanField(verbose_name="Может скачивать аудио", default=False)
    can_view_transcript = models.BooleanField(verbose_name="Может просматривать расшифровку", default=True)
    can_view_summary = models.BooleanField(verbose_name="Может просматривать краткое содержание", default=True)
    can_view_protocol = models.BooleanField(verbose_name="Может смотреть протокол", default=True)
    can_edit_protocol = models.BooleanField(verbose_name="Может редактировать протокол", default=False)
    can_manage_access = models.BooleanField(verbose_name="Может редактировать доступы", default=False)

    granted_by = models.ForeignKey(
        EmployeeModel,
        verbose_name="Кто предоставил доступ",
        on_delete=models.PROTECT,
        related_name="granted_meeting_access",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "employee"],
                name="unique_meeting_employee_access",
            ),
        ]
        verbose_name = "Доступ к совещанию"
        verbose_name_plural = "Доступы к совещаниям"
