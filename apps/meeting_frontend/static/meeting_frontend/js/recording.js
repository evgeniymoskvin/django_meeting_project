(function ($) {
    "use strict";

    const canvas = document.getElementById("waveform");
    const ctx = canvas.getContext("2d");
    const $timer = $("#timer");
    let uploadAfterStop = false;
    let savedRecordingDuration = 0;
    const $recordOrb = $("#record-orb");
    const $orbSymbol = $("#orb-symbol");
    const $statusTitle = $("#status-title");
    const $statusDescription = $("#status-description");
    const $statusDot = $("#status-dot");
    const $saveStatus = $("#save-status");
    const $qualityText = $("#quality-text");
    const $levelHint = $("#level-hint");
    const $db = $("#db-value");
    const $meterSegments = $("#level-meter span");
    const $modal = $("#finish-modal");
    const $toast = $("#toast");

    const $meetingTitle = $("#meeting-title");
    const $meetingTitleInput = $("#meeting-title-input");

    let stream = null;
    let mediaRecorder = null;
    let audioContext = null;
    let analyser = null;
    let sourceNode = null;
    let animationId = null;
    let chunks = [];
    let startedAt = 0;
    let elapsedBeforePause = 0;
    let timerInterval = null;
    let state = "idle"; // idle | recording | paused | stopped | uploading
    let audioBlob = null;
    let bars = [];
    let lastLevel = 0;
    let toastTimeout = null;
    let meetingTitle = (window.RecordingConfig && window.RecordingConfig.initialTitle) || "Совещание";

    function formatTime(totalSeconds) {
        const s = Math.max(0, Math.floor(totalSeconds));
        const h = String(Math.floor(s / 3600)).padStart(2, "0");
        const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
        const sec = String(s % 60).padStart(2, "0");
        return `${h}:${m}:${sec}`;
    }

    function elapsedSeconds() {
        if (state === "recording") return elapsedBeforePause + (Date.now() - startedAt) / 1000;
        return elapsedBeforePause;
    }

    function updateTimer() {
        $timer.text(formatTime(elapsedSeconds()));
    }

    function showToast(message, isError) {
        clearTimeout(toastTimeout);
        $toast.text(message).toggleClass("error", !!isError).addClass("show");
        toastTimeout = setTimeout(() => $toast.removeClass("show"), 3200);
    }

    function setStatus(title, description, active) {
        $statusTitle.text(title);
        $statusDescription.text(description);
        $statusDot.toggleClass("active", !!active);
    }

    function setControls() {
        const recording = state === "recording";
        const paused = state === "paused";
        const hasTake = ["recording", "paused", "stopped"].includes(state);
        $recordOrb
            .toggleClass("is-idle", state === "idle" || state === "stopped")
            .toggleClass("is-paused", false)
            .attr(
                "aria-label",
                state === "recording"
                    ? "Остановить запись и сохранить"
                    : state === "uploading"
                        ? "Идёт сохранение записи"
                        : "Начать запись"
            );
        $orbSymbol.toggleClass("recording-symbol", recording);
        if (state === "idle" || state === "stopped") {
            $orbSymbol.css({
                width: 0,
                height: 0,
                borderTop: "11px solid transparent",
                borderBottom: "11px solid transparent",
                borderLeft: "17px solid white",
                background: "transparent",
                "border-radius": "2px",
                "margin-left": "5px"
            });
        } else {
            $orbSymbol.css({
                width: "21px",
                height: "21px",
                border: "0",
                background: "#fff",
                "border-radius": "4px",
                "margin-left": "0"
            });
        }
    }

    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.floor(rect.width * dpr));
        canvas.height = Math.max(1, Math.floor(rect.height * dpr));
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        bars = Array.from({length: Math.max(48, Math.floor(rect.width / 8))}, () => 0.03 + Math.random() * 0.06);
        drawIdleWave();
    }

    function drawIdleWave() {
        const w = canvas.clientWidth, h = canvas.clientHeight;
        ctx.clearRect(0, 0, w, h);
        const mid = h / 2;
        const count = bars.length || 100;
        const gap = w / count;
        for (let i = 0; i < count; i++) {
            const amp = bars[i] || .04;
            const x = i * gap + gap / 2;
            const half = Math.max(2, amp * h * .85);
            const grad = ctx.createLinearGradient(0, mid - half, 0, mid + half);
            grad.addColorStop(0, "#8caaff");
            grad.addColorStop(.5, "#365ff6");
            grad.addColorStop(1, "#9db6ff");
            ctx.strokeStyle = grad;
            ctx.lineWidth = Math.min(3, Math.max(1.5, gap * .42));
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(x, mid - half);
            ctx.lineTo(x, mid + half);
            ctx.stroke();
        }
    }

    function animateWave() {
        if (!analyser || !audioContext) return;
        const w = canvas.clientWidth, h = canvas.clientHeight, mid = h / 2;
        const data = new Uint8Array(analyser.frequencyBinCount);
        const timeData = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(timeData);
        analyser.getByteFrequencyData(data);
        ctx.clearRect(0, 0, w, h);
        const count = bars.length, gap = w / count;
        let sumSquares = 0;
        for (let i = 0; i < timeData.length; i++) {
            const v = (timeData[i] - 128) / 128;
            sumSquares += v * v;
        }
        const rms = Math.sqrt(sumSquares / timeData.length);
        lastLevel = rms;
        const db = rms > 0.00001 ? Math.max(-60, 20 * Math.log10(rms)) : -60;
        $db.text(`${Math.round(db)} дБ`);
        updateMeter(rms, db);

        for (let i = 0; i < count; i++) {
            const sampleIndex = Math.floor(i * timeData.length / count);
            const v = Math.abs((timeData[sampleIndex] - 128) / 128);
            const freqIndex = Math.min(data.length - 1, Math.floor(i * data.length / count));
            const freq = data[freqIndex] / 255;
            const amp = Math.min(0.95, Math.max(0.025, v * .78 + freq * .22));
            bars[i] = bars[i] * .35 + amp * .65;
            const half = Math.max(2, bars[i] * h * .47);
            const x = i * gap + gap / 2;
            const grad = ctx.createLinearGradient(0, mid - half, 0, mid + half);
            grad.addColorStop(0, "#a9beff");
            grad.addColorStop(.48, "#345cff");
            grad.addColorStop(1, "#a1b8ff");
            ctx.strokeStyle = grad;
            ctx.lineWidth = Math.min(3, Math.max(1.5, gap * .42));
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(x, mid - half);
            ctx.lineTo(x, mid + half);
            ctx.stroke();
        }
        animationId = requestAnimationFrame(animateWave);
    }

    function updateMeter(rms, db) {
        // These are relative signal-level bands, not calibrated sound-pressure dB.
        const normalized = Math.max(0, Math.min(1, (db + 48) / 42));
        const active = Math.round(normalized * $meterSegments.length);
        $meterSegments.each(function (i) {
            $(this).removeClass("on-green on-yellow on-red");
            if (i < active) {
                const ratio = (i + 1) / $meterSegments.length;
                $(this).addClass(ratio > .86 ? "on-red" : (ratio > .62 ? "on-yellow" : "on-green"));
            }
        });
        $(".quality-bars").toggleClass("good", db > -35 && db < -5);
        if (db < -38) {
            $levelHint.text("Сигнал очень тихий. Проверьте расстояние до микрофона.");
            $qualityText.text("Слабый сигнал");
        } else if (db > -5) {
            $levelHint.text("Сигнал слишком высокий — возможны искажения. Уменьшите усиление.");
            $qualityText.text("Возможна перегрузка");
        } else if (db > -35) {
            $levelHint.text("Громкость в норме. Продолжайте в том же темпе.");
            $qualityText.text("Уровень хороший");
        } else {
            $levelHint.text("Сигнал низкий. Убедитесь, что микрофон улавливает речь.");
            $qualityText.text("Проверьте микрофон");
        }
    }

    function stopVisualization() {
        if (animationId) cancelAnimationFrame(animationId);
        animationId = null;
    }

    async function loadMicrophones() {
        try {
            // Permission may be needed before browser reveals device labels.
            const devices = await navigator.mediaDevices.enumerateDevices();
            const $select = $("#microphone-select");
            const previous = $select.val();
            $select.empty();
            devices.filter(d => d.kind === "audioinput").forEach((device, index) => {
                $("<option>").val(device.deviceId).text(device.label || `Микрофон ${index + 1}`).appendTo($select);
            });
            if (!$select.children().length) $("<option>").val("").text("Микрофон по умолчанию").appendTo($select);
            if (previous && $select.find(`option[value="${previous}"]`).length) $select.val(previous);
        } catch (e) {
            console.warn("Не удалось получить список микрофонов", e);
        }
    }

    async function prepareAudio() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Браузер не поддерживает доступ к микрофону. Используйте HTTPS или localhost.");
        }
        const selectedDevice = $("#microphone-select").val();
        const noise = $("#noise-toggle").is(":checked");
        const audioConstraints = {
            echoCancellation: noise,
            noiseSuppression: noise,
            autoGainControl: noise
        };
        if (selectedDevice) audioConstraints.deviceId = {exact: selectedDevice};
        stream = await navigator.mediaDevices.getUserMedia({audio: audioConstraints});
        await loadMicrophones();
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContextClass();
        if (audioContext.state === "suspended") await audioContext.resume();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = .78;
        sourceNode = audioContext.createMediaStreamSource(stream);
        sourceNode.connect(analyser);
        const mimeOptions = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
        const mimeType = mimeOptions.find(type => window.MediaRecorder && MediaRecorder.isTypeSupported(type));
        if (!window.MediaRecorder) throw new Error("Этот браузер не поддерживает MediaRecorder.");
        mediaRecorder = mimeType ? new MediaRecorder(stream, {mimeType}) : new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.addEventListener("dataavailable", event => {
            if (event.data && event.data.size) chunks.push(event.data);
        });

        mediaRecorder.addEventListener("stop", () => {
            const type = mediaRecorder.mimeType || "audio/webm";
            audioBlob = new Blob(chunks, {type});

            if (state !== "uploading") {
                state = "stopped";
                setControls();
            }

            // Отправляем только после формирования окончательного Blob.
            if (uploadAfterStop) {
                uploadAfterStop = false;
                uploadRecording();
            }
        });

        mediaRecorder.start(1000);
    }

    function beginTimer() {
        startedAt = Date.now();
        clearInterval(timerInterval);
        timerInterval = setInterval(updateTimer, 250);
    }

    function stopTimer() {
        if (state === "recording") elapsedBeforePause += (Date.now() - startedAt) / 1000;
        clearInterval(timerInterval);
        timerInterval = null;
        updateTimer();
    }

    function releaseAudio() {
        stopVisualization();
        if (stream) stream.getTracks().forEach(track => track.stop());
        stream = null;
        if (sourceNode) {
            try {
                sourceNode.disconnect();
            } catch (_) {
            }
        }
        sourceNode = null;
        if (audioContext && audioContext.state !== "closed") audioContext.close().catch(() => {
        });
        audioContext = null;
        analyser = null;
    }

    async function startRecording() {
        if (state === "recording" || state === "paused" || state === "uploading") return;
        try {
            await prepareAudio();
            elapsedBeforePause = 0;
            //markers = [];
            //$("#markers-list").empty().prop("hidden", true);
            state = "recording";
            beginTimer();
            setStatus("Идёт запись", "Совещание записывается с микрофона. Говорите в обычном ритме.", true);
            $saveStatus.text("Запись идёт");
            $(".save-indicator i").addClass("active");
            $("#record-hint").html("Запись идёт. Говорите в обычном ритме.<br>Волна показывает входящий уровень сигнала.");
            $recordOrb.find(".orb-pulse").show();
            setControls();
            resizeCanvas();
            animationId = requestAnimationFrame(animateWave);
            await loadMicrophones();
        } catch (error) {
            releaseAudio();
            state = "idle";
            setControls();

            const message = getMicrophoneErrorMessage(error);

            setStatus(
                message.title,
                message.description,
                false
            );

            showToast(message.toast, true);

        }
    }

    function pauseRecording() {
        if (state === "recording") {
            if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.pause();
            stopTimer();
            state = "paused";
            stopVisualization();
            setStatus("Запись на паузе", "Микрофон временно не записывает звук.", false);
            $saveStatus.text("Запись на паузе");
            $("#record-hint").text("Запись приостановлена. Нажмите «Продолжить», чтобы возобновить.");
            $levelHint.text("Измерение уровня приостановлено.");
            setControls();
        } else if (state === "paused") {
            if (mediaRecorder && mediaRecorder.state === "paused") mediaRecorder.resume();
            state = "recording";
            beginTimer();
            setStatus("Идёт запись", "Запись продолжается с того же места.", true);
            $saveStatus.text("Запись идёт");
            $("#record-hint").html("Запись идёт. Говорите в обычном ритме.<br>Волна показывает входящий уровень сигнала.");
            setControls();
            animationId = requestAnimationFrame(animateWave);
        }
    }


    function stopRecording() {
        if (!["recording", "paused"].includes(state)) return;

        // Сохраняем длительность до изменения состояния.
        savedRecordingDuration = Math.floor(elapsedSeconds());
        elapsedBeforePause = savedRecordingDuration;

        // Меняем состояние до остановки таймера,
        // чтобы время не прибавилось повторно.
        state = "stopped";

        stopTimer();
        updateTimer();
        stopVisualization();

        setStatus(
            "Подготавливаем запись",
            "Сохраняем аудио и отправляем его на сервер…",
            false
        );

        $saveStatus.text("Подготовка аудио…");
        $(".save-indicator i").removeClass("active");

        $("#record-hint").text("Запись завершена. Идёт сохранение аудио.");
        $levelHint.text("Измерение уровня завершено.");

        setControls();

        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        } else {
            uploadAfterStop = false;
            showToast("Не удалось остановить запись.", true);
            return;
        }

        releaseAudio();
    }


    function addMarker() {
        if (!["recording", "paused"].includes(state)) return;
        const seconds = Math.floor(elapsedSeconds());
        markers.push(seconds);
        const $list = $("#markers-list").prop("hidden", false);
        $("<span>").addClass("marker-chip").text(`⚑ Отметка ${markers.length} · ${formatTime(seconds)}`).appendTo($list);
        showToast(`Отметка добавлена: ${formatTime(seconds)}`);
    }

    function uploadRecording() {
        if (state === "recording" || state === "paused") stopRecording();
        if (!audioBlob && chunks.length) audioBlob = new Blob(chunks, {type: (mediaRecorder && mediaRecorder.mimeType) || "audio/webm"});
        if (!audioBlob || audioBlob.size === 0) {
            showToast("Нет аудиозаписи для отправки.", true);
            return;
        }
        state = "uploading";
        setControls();

        setStatus("Отправляем запись", "Не закрывайте страницу, пока файл загружается.", false);
        $saveStatus.text("Загрузка аудио…");
        const extension = audioBlob.type.includes("mp4") ? "mp4" : (audioBlob.type.includes("ogg") ? "ogg" : "webm");
        const csrfToken = document.querySelector(
            '#csrf-form [name="csrfmiddlewaretoken"]'
        ).value;
        const participantIds = $("#participants-select").val() || [];
        const formData = new FormData();

        formData.append("audio", audioBlob, `meeting-${Date.now()}.${extension}`);
        formData.append("meeting_title", meetingTitle);
        formData.append(
            "duration_seconds",
            String(savedRecordingDuration)
        );
        participantIds.forEach(id => {
            formData.append("participant_ids", id);
        });
        $.ajax({
            url: window.RecordingConfig.uploadUrl,
            method: "POST",
            data: formData,
            processData: false,
            contentType: false,
            dataType: "json",
            headers: {
                'X-CSRFToken': csrfToken
            },

            success: function (response) {
                state = "stopped";

                $saveStatus.text("Аудио сохранено");
                setStatus(
                    "Совещание сохранено",
                    "Аудиофайл успешно сохранён на сервере.",
                    false
                );

                setControls();
                $recordOrb.prop("disabled", true);

                // Заполняем сведения о сохранённом совещании.
                $("#saved-meeting-title").text(meetingTitle);
                $("#confirm-duration").text(
                    formatTime(savedRecordingDuration)
                );
                $("#saved-filename").text(
                    response.file || "Файл сохранён на сервере"
                );

                // Показываем обязательное модальное окно.
                $modal.prop("hidden", false);

                window.savedMeetingUrl = response.meeting_url;

                // Перемещаем фокус внутрь окна.
                $("#go-transcription").trigger("focus");
                $recordOrb.prop("disabled", true);


            },

            error: function (xhr) {
                state = "stopped";
                setControls();

                const message =
                    xhr.responseJSON && xhr.responseJSON.error
                        ? xhr.responseJSON.error
                        : "Не удалось сохранить совещание. Проверьте соединение и попробуйте ещё раз.";

                setStatus(
                    "Не удалось сохранить совещание",
                    message + " Аудиозапись пока сохранена в памяти браузера.",
                    false
                );

                $saveStatus.text("Ошибка сохранения");

                showToast(message, true);
                showUploadRecoveryActions();
            }
        });
    }


    $("#record-orb").on("click", function () {
        if (state === "idle") {
            startRecording();
            return;
        }

        if (state === "recording" || state === "paused") {
            // Окончательно завершаем запись и отправляем файл.
            uploadAfterStop = true;
            stopRecording();
        }
    });

    $("#cancel-finish").on("click", function () {
        $modal.prop("hidden", true);
    });
    $("#confirm-finish").on("click", function () {
        $modal.prop("hidden", true);
        if (state === "recording" || state === "paused") stopRecording();
        // Let MediaRecorder emit final dataavailable/stop before building the blob.
        window.setTimeout(uploadRecording, 150);
    });
    $("#go-transcription").on("click", function () {
        if (window.savedMeetingUrl) {
            window.location.href = window.savedMeetingUrl;
        }
    });

    function startTitleEditing() {
        if (
            state === "uploading" ||
            state === "paused" ||
            !$meetingTitleInput.prop("hidden")
        ) {
            return;
        }

        $meetingTitleInput
            .val(meetingTitle)
            .prop("hidden", false);

        $meetingTitle.prop("hidden", true);

        $meetingTitleInput.trigger("focus");
        $meetingTitleInput[0].select();
    }

    function finishTitleEditing() {
        if ($meetingTitleInput.prop("hidden")) return;

        const newTitle = $meetingTitleInput.val().trim();

        if (newTitle) {
            meetingTitle = newTitle;
            $meetingTitle.text(meetingTitle);
            document.title = `${meetingTitle} — Протоколы`;
        }

        $meetingTitleInput.prop("hidden", true);
        $meetingTitle.prop("hidden", false);
    }

    $meetingTitle.on("click", startTitleEditing);

    $meetingTitle.on("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            startTitleEditing();
        }
    });

    $meetingTitleInput.on("blur", finishTitleEditing);

    $meetingTitleInput.on("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            this.blur();
        }

        if (event.key === "Escape") {
            $meetingTitleInput.val(meetingTitle);
            this.blur();
        }
    });
    $(document).on("keydown", function (event) {
        //if (event.key === "Escape") $modal.prop("hidden", true);
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "m") {
            event.preventDefault();
            addMarker();
        }
    });
    $(window).on("resize", resizeCanvas);
    $(async function () {
        resizeCanvas();
        setControls();
        await loadMicrophones();
    });


    function getMicrophoneErrorMessage(error) {
        switch (error?.name) {
            case "NotFoundError":
            case "DevicesNotFoundError":
                return {
                    title: "Микрофон не найден",
                    description: "Подключите микрофон и попробуйте снова.",
                    toast: "Не удалось найти микрофон. Проверьте подключение."
                };

            case "NotAllowedError":
            case "PermissionDeniedError":
            case "SecurityError":
                return {
                    title: "Нет доступа к микрофону",
                    description: "Разрешите браузеру использовать микрофон и повторите попытку.",
                    toast: "Разрешите доступ к микрофону в настройках браузера."
                };

            case "NotReadableError":
            case "TrackStartError":
                return {
                    title: "Микрофон занят",
                    description: "Закройте другие приложения, использующие микрофон, и попробуйте снова.",
                    toast: "Микрофон занят или недоступен. Проверьте подключение."
                };

            case "OverconstrainedError":
            case "ConstraintNotSatisfiedError":
                return {
                    title: "Не удалось выбрать микрофон",
                    description: "Выберите другое устройство или микрофон по умолчанию.",
                    toast: "Выбранный микрофон недоступен. Выберите другой."
                };

            default:
                return {
                    title: "Не удалось запустить запись",
                    description: "Проверьте подключение микрофона и разрешения браузера.",
                    toast: "Не удалось запустить запись. Проверьте микрофон."
                };
        }
    }


    function showUploadRecoveryActions() {
        $("#upload-recovery-actions").remove();

        const $actions = $(`
        <div id="upload-recovery-actions" class="upload-recovery">
            <div class="upload-recovery__heading">
                <span class="upload-recovery__icon">!</span>
                <div>
                    <div class="upload-recovery__title">
                        Аудиозапись не потеряна
                    </div>
                    <div class="upload-recovery__text">
                        Попробуйте отправить её ещё раз или скачайте файл на компьютер.
                    </div>
                </div>
            </div>

            <div class="upload-recovery__buttons">
                <button type="button" id="retry-upload"
                        class="upload-recovery__button upload-recovery__button--primary">
                    <span class="upload-recovery__button-icon">↻</span>
                    Повторить отправку
                </button>

                <button type="button" id="download-audio"
                        class="upload-recovery__button upload-recovery__button--secondary">
                    <span class="upload-recovery__button-icon">↓</span>
                    Скачать аудио
                </button>
            </div>
        </div>
    `);

        $statusDescription.after($actions);

        $("#retry-upload").on("click", function () {
            if (!audioBlob || audioBlob.size === 0) {
                showToast("Аудиозапись недоступна.", true);
                return;
            }

            uploadRecording();
        });

        $("#download-audio").on("click", function () {
            if (!audioBlob || audioBlob.size === 0) {
                showToast("Аудиозапись недоступна.", true);
                return;
            }

            const extension = audioBlob.type.includes("mp4")
                ? "mp4"
                : audioBlob.type.includes("ogg")
                    ? "ogg"
                    : "webm";

            const url = URL.createObjectURL(audioBlob);
            const link = document.createElement("a");

            link.href = url;
            link.download = `meeting-${Date.now()}.${extension}`;

            document.body.appendChild(link);
            link.click();
            link.remove();

            setTimeout(() => URL.revokeObjectURL(url), 1000);
        });
    }


})(jQuery);
