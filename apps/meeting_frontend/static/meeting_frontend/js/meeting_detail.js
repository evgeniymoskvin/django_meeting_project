(function ($) {
    "use strict";

    $(function () {
        const audio = document.getElementById("meeting-audio");

        if (!audio) return;

        const $play = $("#audio-play");
        const $playIcon = $("#audio-play-icon");
        const $seek = $("#audio-seek");
        const $current = $("#audio-current-time");
        const $total = $("#audio-total-time");
        const $speed = $("#audio-speed");
        let pendingSeek = null;

        let seeking = false;

        function formatTime(seconds) {
            if (!Number.isFinite(seconds) || seconds < 0) {
                return "00:00";
            }

            const value = Math.floor(seconds);
            const hours = Math.floor(value / 3600);
            const minutes = Math.floor((value % 3600) / 60);
            const secs = value % 60;

            if (hours > 0) {
                return [
                    hours,
                    String(minutes).padStart(2, "0"),
                    String(secs).padStart(2, "0")
                ].join(":");
            }

            return [
                String(minutes).padStart(2, "0"),
                String(secs).padStart(2, "0")
            ].join(":");
        }

        function updatePlayButton() {
            const playing = !audio.paused && !audio.ended;

            $playIcon.text(playing ? "Ⅱ" : "▶");
            $play.attr(
                "aria-label",
                playing ? "Приостановить воспроизведение" : "Воспроизвести аудиозапись"
            );
        }

        function updateProgress() {
            $current.text(formatTime(audio.currentTime));

            if (
                !seeking &&
                Number.isFinite(audio.duration) &&
                audio.duration > 0
            ) {
                $seek.val((audio.currentTime / audio.duration) * 100);
            }
        }

        function updateDuration() {
            const duration = audio.duration;

            if (Number.isFinite(duration) && duration > 0) {
                $total.text(formatTime(duration));
                $seek.prop("disabled", false);
            } else {
                // Не блокируем ползунок только из-за того,
                // что браузер ещё не определил длительность.
                $total.text("--:--");
                $seek.prop("disabled", false);
            }
        }

        $play.on("click", function () {
            if (audio.paused) {
                audio.play().catch(function () {
                    updatePlayButton();
                });
            } else {
                audio.pause();
            }
        });

// Когда длительность аудио стала известна
        audio.addEventListener("loadedmetadata", updateDuration);
        audio.addEventListener("durationchange", updateDuration);
        audio.addEventListener("canplay", updateDuration);
        audio.addEventListener("timeupdate", updateProgress);

        audio.addEventListener("play", updatePlayButton);
        audio.addEventListener("pause", updatePlayButton);
        audio.addEventListener("ended", updatePlayButton);

        // При перемещении ползунка показываем выбранное время
        $seek.on("input", function () {
            seeking = true;

            const duration = audio.duration;
            const percent = Number(this.value);

            if (Number.isFinite(duration) && duration > 0) {
                pendingSeek = duration * percent / 100;
                $current.text(formatTime(pendingSeek));
            }
        });

// При отпускании ползунка меняем позицию аудио
        $seek.on("change", function () {
            const duration = audio.duration;
            const percent = Number(this.value);

            if (Number.isFinite(duration) && duration > 0) {
                pendingSeek = duration * percent / 100;

                try {
                    audio.currentTime = pendingSeek;
                } catch (error) {
                    console.error("Ошибка перемотки аудио:", error);
                }
            }

            seeking = false;
        });

        audio.addEventListener("seeked", function () {
            pendingSeek = null;
            updateProgress();
        });

        audio.addEventListener("timeupdate", function () {
            if (pendingSeek === null) {
                updateProgress();
            }
        });

        $("#audio-back").on("click", function () {
            audio.currentTime = Math.max(0, audio.currentTime - 15);
        });

        $("#audio-forward").on("click", function () {
            const end = Number.isFinite(audio.duration)
                ? audio.duration
                : audio.currentTime + 15;

            audio.currentTime = Math.min(end, audio.currentTime + 15);
        });

        $speed.on("change", function () {
            audio.playbackRate = Number(this.value) || 1;
        });

        // Форматируем длительность совещания в заголовке.
        const $duration = $("#meeting-duration");
        const seconds = Number($duration.data("seconds"));

        if (Number.isFinite(seconds)) {
            $duration.text(formatTime(seconds));
        }

        updatePlayButton();
    });
})(jQuery);
