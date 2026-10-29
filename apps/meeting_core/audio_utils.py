import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.exceptions import ValidationError


def save_audio_as_mp3(meeting, uploaded_file):
    """
    Конвертирует загруженное аудио в MP3 и сохраняет
    результат в meeting.audio_file.

    meeting — уже сохранённый объект MeetingModel.
    uploaded_file — файл из request.FILES.
    """
    ffmpeg_binary = settings.FFMPEG_BINARY

    with tempfile.TemporaryDirectory(prefix="meeting_audio_") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "input_audio"
        output_path = temp_path / "output_audio.mp3"

        # Записываем загруженный файл во временное хранилище,
        # не загружая целиком в оперативную память.
        with input_path.open("wb") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        command = [
            ffmpeg_binary,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(input_path),
            "-map", "0:a:0",
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60 * 30,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "FFmpeg не найден. Проверьте установку "
                "и настройку FFMPEG_BINARY."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ValidationError(
                "Превышено время обработки аудиозаписи."
            ) from exc

        if result.returncode != 0 or not output_path.exists():
            # Не записываем в модель повреждённый результат.
            raise ValidationError(
                "Не удалось преобразовать аудиозапись в MP3."
            )

        if output_path.stat().st_size == 0:
            raise ValidationError(
                "FFmpeg создал пустой аудиофайл."
            )

        # Сохраняем через Django Storage, а не напрямую
        # в каталог MEDIA_ROOT. Это совместимо с разными
        # настройками файлового хранилища.
        with output_path.open("rb") as converted_file:
            meeting.audio_file.save(
                f"{meeting.pk}.mp3",
                File(converted_file),
                save=False,
            )

        meeting.save(update_fields=["audio_file"])
