package vn.pocketcanvas

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.IBinder
import java.io.File

/** Keeps the loopback OpenAI-compatible endpoint alive while the user switches to LocalMind. */
class LocalImageApiService : Service() {
    private var apiServer: LocalImageApiServer? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(NOTIFICATION_ID, buildNotification("Khởi động local API…"))
        val path = intent?.getStringExtra(EXTRA_MODEL_PATH)
        val token = intent?.getStringExtra(EXTRA_TOKEN)
        val model = path?.let(::File)
        if (model == null || token.isNullOrBlank() || !ModelPackage.isValid(model)) {
            publish("Không mở được API: chưa cài model hợp lệ.")
            stopSelf()
            return START_NOT_STICKY
        }
        apiServer?.stop()
        val server = LocalImageApiServer(applicationContext, model, token, ::publish)
        return try {
            server.start()
            apiServer = server
            publish("Đã bật API cho LocalMind tại 127.0.0.1:${LocalImageApiServer.PORT}.")
            START_REDELIVER_INTENT
        } catch (error: Exception) {
            server.stop()
            apiServer = null
            publish("Không bật được API: cổng ${LocalImageApiServer.PORT} có thể đang được dùng.")
            stopSelf()
            START_NOT_STICKY
        }
    }

    override fun onDestroy() {
        getSharedPreferences("pocketcanvas", MODE_PRIVATE).edit().putBoolean("localmind_api_enabled", false).apply()
        apiServer?.stop()
        apiServer = null
        Thread({ DiffusionRuntime.close() }, "pocketcanvas-model-release").apply {
            isDaemon = true
            start()
        }
        publish("Local API đã tắt.")
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun publish(message: String) {
        currentStatus = message
        statusListener?.invoke(message)
        try {
            getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, buildNotification(message))
        } catch (_: Exception) { }
    }

    private fun buildNotification(message: String): Notification {
        createNotificationChannel()
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopService = PendingIntent.getService(
            this,
            1,
            Intent(this, LocalImageApiService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_gallery)
            .setContentTitle("PocketCanvas · LocalMind API")
            .setContentText(message.take(110))
            .setContentIntent(openApp)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Tắt API", stopService)
            .build()
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        if (manager.getNotificationChannel(CHANNEL_ID) == null) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "PocketCanvas local API", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    companion object {
        const val ACTION_STOP = "vn.pocketcanvas.action.STOP_LOCAL_API"
        const val EXTRA_MODEL_PATH = "model_path"
        const val EXTRA_TOKEN = "api_token"
        const val CHANNEL_ID = "pocketcanvas-local-api"
        const val NOTIFICATION_ID = 4207
        @Volatile var statusListener: ((String) -> Unit)? = null
        @Volatile var currentStatus: String = "Local API đang tắt."
    }
}
