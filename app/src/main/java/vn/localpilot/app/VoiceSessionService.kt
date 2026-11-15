package vn.localpilot.app

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/** User-started, time-limited, on-device-only voice session with an ongoing notification. */
class VoiceSessionService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var paused = true
    private var listening = false
    private var consecutiveErrors = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> beginSession()
            ACTION_RESUME -> {
                if (VoiceSessionState.active.value && VoiceSessionState.pendingCommand.value == null) {
                    paused = false
                    VoiceSessionState.setStatus("Đang nghe lệnh tiếng Việt ngoại tuyến.")
                    updateNotification("Đang nghe lệnh · nói “dừng” để kết thúc phiên")
                    startListening()
                } else if (VoiceSessionState.pendingCommand.value != null) {
                    VoiceSessionState.setStatus("Một lệnh đang chờ bạn xem. Dùng hoặc bỏ qua lệnh trước khi tiếp tục nghe.")
                }
            }
            ACTION_PAUSE -> {
                paused = true
                cancelListening()
                VoiceSessionState.setStatus("Đã tạm dừng nghe để chờ bạn xem lệnh.")
                updateNotification("Tạm dừng nghe · mở LocalPilot để xem lệnh")
            }
            ACTION_STOP -> {
                VoiceSessionState.setStatus("Bạn đã dừng phiên nghe.")
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun beginSession() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            !SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            VoiceSessionState.setActive(false)
            VoiceSessionState.setStatus("Thiết bị chưa có nhận dạng giọng nói ngoại tuyến. Cài dịch vụ/ngôn ngữ vi-VN; không dùng nhận dạng trực tuyến thay thế.")
            stopSelf()
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            VoiceSessionState.setActive(false)
            VoiceSessionState.setStatus("Chưa được cấp quyền micro; phiên nghe chưa bắt đầu.")
            stopSelf()
            return
        }
        createNotificationChannel()
        val notification = buildNotification("Đang khởi động nhận dạng tiếng Việt trên thiết bị…")
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        }.onFailure {
            VoiceSessionState.setActive(false)
            VoiceSessionState.setStatus("Android không cho phép khởi động dịch vụ micro: ${it.message ?: "kiểm tra quyền và thử khi LocalPilot đang mở"}")
            stopSelf()
            return
        }
        isForeground = true
        VoiceSessionState.setActive(true)
        VoiceSessionState.setStatus("Đang nghe lệnh tiếng Việt ngoại tuyến. Nói “dừng” để kết thúc phiên.")
        paused = false
        consecutiveErrors = 0
        handler.removeCallbacks(stopForTimeout)
        handler.postDelayed(stopForTimeout, MAX_SESSION_MS)
        startListening()
    }

    private val stopForTimeout = Runnable {
        VoiceSessionState.setStatus("Phiên giọng nói đã tự kết thúc sau 20 phút.")
        stopSelf()
    }

    private fun startListening() {
        if (paused || listening || !VoiceSessionState.active.value) return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S || !SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            VoiceSessionState.setStatus("Dịch vụ nhận dạng ngoại tuyến không còn khả dụng trên thiết bị.")
            stopSelf()
            return
        }
        val current = recognizer ?: runCatching {
            SpeechRecognizer.createOnDeviceSpeechRecognizer(this).also { created ->
                created.setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) {
                        VoiceSessionState.setStatus("Đang nghe lệnh tiếng Việt ngoại tuyến. Nói “dừng” để kết thúc phiên.")
                    }
                    override fun onBeginningOfSpeech() = Unit
                    override fun onRmsChanged(rmsdB: Float) = Unit
                    override fun onBufferReceived(buffer: ByteArray?) = Unit
                    override fun onEndOfSpeech() = Unit
                    override fun onPartialResults(partialResults: Bundle?) = Unit
                    override fun onEvent(eventType: Int, params: Bundle?) = Unit

                    override fun onResults(results: Bundle?) {
                        listening = false
                        consecutiveErrors = 0
                        val phrase = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                            ?.firstOrNull()?.trim()?.take(MAX_COMMAND_LENGTH).orEmpty()
                        if (phrase.isBlank()) {
                            restartListeningSoon()
                        } else if (isStopCommand(phrase)) {
                            ScreenAccessService.cancelAutomation()
                            VoiceSessionState.setStatus("Đã nhận lệnh dừng; phiên nghe đã kết thúc.")
                            stopSelf()
                        } else {
                            paused = true
                            VoiceSessionState.postCommand(phrase)
                            VoiceSessionState.setStatus("Đã nhận “$phrase”. Mở LocalPilot để xem lệnh; chưa có thao tác nào chạy.")
                            updateNotification("Đã nhận lệnh · chạm để xem")
                        }
                    }

                    override fun onError(error: Int) {
                        listening = false
                        if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
                            restartListeningSoon()
                        } else if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                            VoiceSessionState.setStatus("Quyền micro đã bị thu hồi; phiên nghe đã kết thúc.")
                            stopSelf()
                        } else {
                            consecutiveErrors++
                            if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                                VoiceSessionState.setStatus("Nhận dạng thất bại (mã $error). Kiểm tra gói tiếng Việt ngoại tuyến.")
                                stopSelf()
                            } else {
                                restartListeningSoon()
                            }
                        }
                    }
                })
            }
        }.getOrElse {
            VoiceSessionState.setStatus("Không khởi tạo được dịch vụ nhận dạng ngoại tuyến: ${it.message ?: "lỗi hệ thống"}")
            stopSelf()
            return
        }
        recognizer = current
        val request = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "vi-VN")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "vi-VN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        runCatching {
            listening = true
            current.startListening(request)
        }.onFailure {
            listening = false
            consecutiveErrors++
            if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                VoiceSessionState.setStatus("Không bắt đầu được nhận dạng tiếng Việt ngoại tuyến: ${it.message ?: "kiểm tra dịch vụ nhận dạng trên thiết bị"}")
                stopSelf()
            } else {
                restartListeningSoon()
            }
        }
    }

    private fun restartListeningSoon() {
        if (paused || !VoiceSessionState.active.value) return
        handler.removeCallbacks(restartListening)
        handler.postDelayed(restartListening, LISTEN_RETRY_DELAY_MS)
    }

    private val restartListening = Runnable { startListening() }

    private fun cancelListening() {
        handler.removeCallbacks(restartListening)
        if (listening) runCatching { recognizer?.cancel() }
        listening = false
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Phiên giọng nói LocalPilot", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Thông báo thường trực khi LocalPilot đang nghe tiếng Việt ngoại tuyến."
                }
            )
        }
    }

    private fun buildNotification(message: String): Notification {
        val openApp = PendingIntent.getActivity(
            this, OPEN_APP_REQUEST,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stop = PendingIntent.getService(
            this, STOP_REQUEST,
            Intent(this, VoiceSessionService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("LocalPilot · phiên giọng nói")
            .setContentText(message)
            .setContentIntent(openApp)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(android.R.drawable.ic_media_pause, "Dừng phiên", stop)
            .build()
    }

    private fun updateNotification(message: String) {
        if (!VoiceSessionState.active.value) return
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, buildNotification(message))
    }

    private fun isStopCommand(text: String): Boolean {
        val normalized = text.lowercase().trim().trimEnd('.', '!', '?', ',', ';', ':').replace(Regex("\\s+"), " ")
        return normalized in STOP_COMMANDS
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        runCatching { recognizer?.cancel() }
        recognizer?.destroy()
        recognizer = null
        listening = false
        VoiceSessionState.setActive(false)
        if (isForeground) runCatching { stopForeground(STOP_FOREGROUND_REMOVE) }
        super.onDestroy()
    }

    private var isForeground = false

    companion object {
        const val ACTION_START = "vn.localpilot.app.voice.START"
        const val ACTION_RESUME = "vn.localpilot.app.voice.RESUME"
        const val ACTION_PAUSE = "vn.localpilot.app.voice.PAUSE"
        const val ACTION_STOP = "vn.localpilot.app.voice.STOP"
        private const val CHANNEL_ID = "localpilot_voice_session"
        private const val NOTIFICATION_ID = 4812
        private const val OPEN_APP_REQUEST = 4813
        private const val STOP_REQUEST = 4814
        private const val MAX_SESSION_MS = 20 * 60 * 1000L
        private const val LISTEN_RETRY_DELAY_MS = 500L
        private const val MAX_CONSECUTIVE_ERRORS = 4
        private const val MAX_COMMAND_LENGTH = 1_000
        private val STOP_COMMANDS = setOf(
            "dừng", "dừng lại", "dừng bot", "dừng macro", "dừng thao tác", "dừng kế hoạch",
            "hãy dừng", "hãy dừng lại", "hủy", "huỷ", "hủy macro", "huỷ macro", "stop", "stop macro"
        )
    }
}
