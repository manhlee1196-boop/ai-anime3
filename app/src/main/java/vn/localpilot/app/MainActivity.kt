package vn.localpilot.app

import android.Manifest
import android.content.ComponentName
import android.content.Intent
import android.content.ServiceConnection
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.StopCircle
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import rikka.shizuku.Shizuku
import java.io.File

private val Ink = Color(0xFF172225)
private val Muted = Color(0xFF687778)
private val Green = Color(0xFFB6F36A)
private val Canvas = Color(0xFFF4F7F4)
private val Border = Color(0xFFE3E9E4)

class MainActivity : ComponentActivity() {
    private var shizukuResultCallback: ((String) -> Unit)? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var speechResultCallback: ((Result<String>) -> Unit)? = null
    private val shizukuUserServiceArgs by lazy {
        Shizuku.UserServiceArgs(ComponentName(this, ShizukuDiagnosticService::class.java))
            .tag("localpilot-diagnostic")
            .daemon(false)
            .processNameSuffix("diagnostic")
            .debuggable(false)
            .version(1)
    }
    private val shizukuConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val remote = service?.let { IShizukuDiagnostic.Stub.asInterface(it) }
            if (remote == null) {
                finishShizukuCheck("Không nhận được dịch vụ Shizuku.")
                return
            }
            lifecycleScope.launch {
                val result = withContext(Dispatchers.IO) {
                    runCatching {
                        val count = remote.countUserApps()
                        if (count < 0) "Lệnh chẩn đoán Shizuku thất bại hoặc quá thời gian chờ."
                        else "Kết nối Shizuku OK · phát hiện $count ứng dụng người dùng. Không có lệnh nào thay đổi hệ thống."
                    }.getOrElse { "Không gọi được dịch vụ Shizuku: ${it.message ?: "lỗi không xác định"}" }
                }
                finishShizukuCheck(result)
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            if (shizukuResultCallback != null) finishShizukuCheck("Dịch vụ Shizuku đã ngắt kết nối.")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        val localModel = LocalModel(applicationContext)
        val modelFile = File(File(filesDir, "models"), "assistant.litertlm")
        setContent {
            MaterialTheme {
                PilotApp(
                    model = localModel,
                    existingModel = modelFile.takeIf { it.exists() },
                    accessibilityEnabled = { isScreenAccessEnabled() },
                    openAccessibilitySettings = { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) },
                    requestShizukuPermission = { requestShizukuPermission() },
                    runShizukuCheck = { callback -> runShizukuCheck(callback) }
                )
            }
        }
    }

    fun startVietnameseVoiceRecognition(onResult: (Result<String>) -> Unit) {
        if (speechRecognizer != null) {
            onResult(Result.failure(IllegalStateException("Đang nghe một lượt; đợi kết quả trước khi nói tiếp.")))
            return
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            onResult(Result.failure(IllegalStateException("Nhận dạng giọng nói ngoại tuyến chỉ được hỗ trợ từ Android 12 trở lên.")))
            return
        }
        if (!SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            onResult(Result.failure(IllegalStateException("Thiết bị chưa có dịch vụ nhận dạng giọng nói trên máy. Không dùng nhận dạng trực tuyến thay thế.")))
            return
        }
        speechRecognizer?.destroy()
        speechResultCallback = onResult
        val recognizer = runCatching { SpeechRecognizer.createOnDeviceSpeechRecognizer(this) }
            .getOrElse {
                speechResultCallback = null
                onResult(Result.failure(IllegalStateException("Không khởi tạo được nhận dạng ngoại tuyến: ${it.message ?: "lỗi không xác định"}")))
                return
            }
        speechRecognizer = recognizer
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) = Unit
            override fun onBeginningOfSpeech() = Unit
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() = Unit
            override fun onEvent(eventType: Int, params: Bundle?) = Unit
            override fun onPartialResults(partialResults: Bundle?) = Unit

            override fun onError(error: Int) {
                finishSpeechRecognition(Result.failure(IllegalStateException(speechErrorMessage(error))))
            }

            override fun onResults(results: Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim()
                if (text.isNullOrBlank()) finishSpeechRecognition(Result.failure(IllegalStateException("Không nhận ra lời nói. Hãy thử nói lại rõ hơn.")))
                else finishSpeechRecognition(Result.success(text))
            }
        })
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "vi-VN")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "vi-VN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        }
        runCatching { recognizer.startListening(intent) }
            .onFailure { finishSpeechRecognition(Result.failure(IllegalStateException("Không bắt đầu được nhận dạng: ${it.message ?: "lỗi không xác định"}"))) }
    }

    fun cancelVietnameseVoiceRecognition() {
        speechResultCallback = null
        speechRecognizer?.cancel()
        speechRecognizer?.destroy()
        speechRecognizer = null
    }

    private fun finishSpeechRecognition(result: Result<String>) {
        val callback = speechResultCallback ?: return
        speechResultCallback = null
        speechRecognizer?.destroy()
        speechRecognizer = null
        callback(result)
    }

    private fun speechErrorMessage(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_AUDIO -> "Lỗi ghi âm. Kiểm tra micro rồi thử lại."
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Chưa được cấp quyền micro."
        SpeechRecognizer.ERROR_NETWORK,
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Nhận dạng ngoại tuyến không khả dụng lúc này; không gửi âm thanh lên mạng."
        SpeechRecognizer.ERROR_NO_MATCH,
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Không nhận ra lời nói. Hãy thử nói lại rõ hơn."
        else -> "Nhận dạng tiếng Việt thất bại (mã $error). Kiểm tra gói ngôn ngữ nhận dạng ngoại tuyến trên thiết bị."
    }

    override fun onDestroy() {
        speechResultCallback = null
        speechRecognizer?.cancel()
        speechRecognizer?.destroy()
        speechRecognizer = null
        super.onDestroy()
    }

    private fun isScreenAccessEnabled(): Boolean {
        val expected = ComponentName(this, ScreenAccessService::class.java).flattenToString()
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        return enabled?.split(':')?.any { it.equals(expected, ignoreCase = true) } == true
    }

    private fun requestShizukuPermission(): String = try {
        if (!Shizuku.pingBinder()) {
            "Shizuku chưa chạy. Mở Shizuku và khởi động dịch vụ trước."
        } else if (Shizuku.checkSelfPermission() == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            "Đã có quyền Shizuku."
        } else {
            Shizuku.requestPermission(SHIZUKU_REQUEST_CODE)
            "Đã gửi yêu cầu quyền. Chấp thuận trong Shizuku, sau đó nhấn kiểm tra lại."
        }
    } catch (_: Exception) {
        "Không kết nối được Shizuku. Hãy kiểm tra ứng dụng Shizuku và thử lại."
    }

    private fun runShizukuCheck(onResult: (String) -> Unit) {
        try {
            if (!Shizuku.pingBinder()) {
                onResult("Shizuku chưa chạy. Mở Shizuku và khởi động dịch vụ trước.")
                return
            }
            if (Shizuku.checkSelfPermission() != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                onResult("Chưa cấp quyền Shizuku. Nhấn Cấp quyền trước.")
                return
            }
            shizukuResultCallback = onResult
            onResult("Đang kết nối UserService chỉ-đọc…")
            Shizuku.bindUserService(shizukuUserServiceArgs, shizukuConnection)
            lifecycleScope.launch {
                delay(12_000)
                if (shizukuResultCallback === onResult) finishShizukuCheck("Shizuku không phản hồi trong thời gian chờ.")
            }
        } catch (e: Exception) {
            shizukuResultCallback = null
            onResult("Kiểm tra Shizuku thất bại: ${e.message ?: "lỗi không xác định"}")
        }
    }

    private fun finishShizukuCheck(message: String) {
        val callback = shizukuResultCallback ?: return
        shizukuResultCallback = null
        callback(message)
        runCatching { Shizuku.unbindUserService(shizukuUserServiceArgs, shizukuConnection, true) }
    }

    companion object { private const val SHIZUKU_REQUEST_CODE = 7341 }
}

private data class ChatLine(val fromUser: Boolean, val text: String)

private fun emptyUiActions(): List<UiAction> = emptyList()

internal sealed interface UiAction {
    val label: String
    data class Tap(override val label: String) : UiAction
    data class Type(override val label: String, val text: String) : UiAction
}

@Composable
private fun PilotApp(
    model: LocalModel,
    existingModel: File?,
    accessibilityEnabled: () -> Boolean,
    openAccessibilitySettings: () -> Unit,
    requestShizukuPermission: () -> String,
    runShizukuCheck: ((String) -> Unit) -> Unit
) {
    val context = LocalContext.current
    val activity = context as? MainActivity
    val messages: SnapshotStateList<ChatLine> = remember { mutableStateListOf() }
    var input by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(existingModel != null) }
    var modelStatus by remember { mutableStateOf(if (existingModel != null) "Đang nạp mô hình…" else "Chưa có mô hình") }
    var modelReady by remember { mutableStateOf(false) }
    var screenReady by remember { mutableStateOf(false) }
    var screenText by remember { mutableStateOf(null as String?) }
    var screenPackage by remember { mutableStateOf(null as String?) }
    var screenPreview by remember { mutableStateOf("") }
    var waitingForScreenCapture by remember { mutableStateOf(false) }
    var pendingActions by remember { mutableStateOf(emptyUiActions()) }
    var pendingTargetPackage by remember { mutableStateOf(null as String?) }
    var actionStatus by remember { mutableStateOf("") }
    var voiceStatus by remember { mutableStateOf("Nhấn micro để nói một câu tiếng Việt; không nghe nền.") }
    var voiceListening by remember { mutableStateOf(false) }
    var shizukuStatus by remember { mutableStateOf("Chưa kiểm tra · tùy chọn") }
    val focusManager = LocalFocusManager.current

    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null && activity != null) {
            activity.lifecycleScope.launch {
                busy = true
                modelStatus = "Đang nhập model vào bộ nhớ riêng…"
                runCatching { model.importModel(uri) }
                    .onSuccess { file ->
                        modelStatus = "Đang nạp model · ${file.length() / (1024 * 1024)} MB"
                        runCatching { model.load(file) }
                            .onSuccess { modelReady = true; modelStatus = "Mô hình đã sẵn sàng · chạy ngoại tuyến" }
                            .onFailure { modelReady = false; modelStatus = "Không nạp được mô hình: ${it.message ?: "không tương thích"}" }
                    }
                    .onFailure { modelStatus = "Không nhập được model: ${it.message ?: "lỗi đọc tệp"}" }
                busy = false
            }
        }
    }

    LaunchedEffect(existingModel) {
        if (existingModel != null && activity != null) {
            runCatching { model.load(existingModel) }
                .onSuccess { modelReady = true; modelStatus = "Mô hình đã sẵn sàng · chạy ngoại tuyến" }
                .onFailure { modelStatus = "Không nạp được mô hình: ${it.message ?: "không tương thích"}" }
            busy = false
        }
    }
    LaunchedEffect(Unit) { screenReady = accessibilityEnabled() }
    DisposableEffect(activity) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                screenReady = accessibilityEnabled()
                val captured = ScreenAccessService.consumeCapturedScreen()
                if (captured != null) {
                    waitingForScreenCapture = false
                    screenText = captured.text
                    screenPackage = captured.packageName
                    screenPreview = captured.text.take(1_500)
                } else if (waitingForScreenCapture) {
                    waitingForScreenCapture = false
                    ScreenAccessService.cancelScreenCapture()
                    screenPreview = "Không chụp được văn bản app đích. Hãy thử lại và giữ app mở cho đến khi màn hình tải xong."
                }
                ScreenAccessService.consumeActionResult()?.let { actionStatus = it }
            }
            if (event == Lifecycle.Event.ON_STOP) {
                screenText = null
                screenPackage = null
                screenPreview = ""
                if (pendingActions.isNotEmpty()) {
                    pendingActions = emptyList()
                    pendingTargetPackage = null
                    actionStatus = "Kế hoạch chưa được duyệt đã hủy khi app rời nền."
                }
            }
        }
        activity?.lifecycle?.addObserver(observer)
        onDispose { activity?.lifecycle?.removeObserver(observer) }
    }

    val sendMessage: (String?) -> Unit = { spokenText ->
        val question = (spokenText ?: input).trim()
        if (question.isNotEmpty() && modelReady && !busy && activity != null) {
            input = ""
            focusManager.clearFocus()
            val history = messages.takeLast(8).joinToString("\n") { line ->
                "${if (line.fromUser) "User" else "Assistant"}: ${line.text}"
            }
            if (waitingForScreenCapture) {
                ScreenAccessService.cancelScreenCapture()
                waitingForScreenCapture = false
            }
            messages.add(ChatLine(true, question))
            busy = true
            pendingActions = emptyList()
            pendingTargetPackage = null
            actionStatus = ""
            val contextualScreen = screenText
            val contextualPackage = screenPackage
            screenText = null
            screenPackage = null
            screenPreview = ""
            activity.lifecycleScope.launch {
                runCatching { model.respond(question, contextualScreen, history) }
                    .onSuccess { raw ->
                        val planLine = raw.lineSequence().firstOrNull { it.trimStart().startsWith("ACTION_PLAN_JSON:") }
                        val explicitlyRequested = ACTION_INTENT_WORDS.any { word -> question.contains(word, ignoreCase = true) }
                        val appVisible = activity.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)
                        val plan = if (planLine != null && explicitlyRequested && appVisible && contextualScreen != null && contextualPackage != null) {
                            parseActionPlan(planLine, contextualScreen, question)
                        } else emptyList()
                        val visibleAnswer = raw.lineSequence()
                            .filterNot { it.trimStart().startsWith("ACTION_PLAN_JSON:") }
                            .joinToString("\n").trim().ifBlank {
                                if (plan.isNotEmpty()) "Mình đã soạn một kế hoạch thao tác. Hãy kiểm tra từng bước và duyệt nếu đúng."
                                else "Mình chưa thể thực hiện yêu cầu đó."
                            }
                        messages.add(ChatLine(false, visibleAnswer))
                        pendingActions = plan
                        pendingTargetPackage = if (plan.isNotEmpty()) contextualPackage else null
                        if (planLine != null && plan.isEmpty()) {
                            actionStatus = "Đã chặn kế hoạch: yêu cầu chưa rõ, nhãn không khớp màn hình hoặc có bước không an toàn."
                        }
                    }
                    .onFailure {
                        messages.add(ChatLine(false, "Lỗi chạy model trên thiết bị: ${it.message ?: "không rõ nguyên nhân"}. Hãy thử model LiteRT-LM tương thích và kiểm tra bộ nhớ trống."))
                    }
                busy = false
            }
        }
    }

    val handleVoiceResult: (Result<String>) -> Unit = { result ->
        voiceListening = false
        result.onSuccess { recognized ->
            val utterance = recognized.trim()
            voiceStatus = "Đã nhận: $utterance"
            if (isStopVoiceCommand(utterance)) {
                val hadAutomation = ScreenAccessService.cancelAutomation()
                pendingActions = emptyList()
                pendingTargetPackage = null
                actionStatus = if (hadAutomation) {
                    "Đã nhận lệnh dừng. Macro sẽ dừng trước bước tiếp theo; thao tác đang diễn ra có thể hoàn tất."
                } else {
                    "Đã nhận lệnh dừng. Không có macro nào đang chờ hoặc chạy."
                }
            } else {
                input = utterance
                sendMessage(utterance)
            }
        }.onFailure { error ->
            voiceStatus = error.message ?: "Không nhận được giọng nói."
        }
    }
    val voicePermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && activity != null) {
            voiceListening = true
            voiceStatus = "Đang nghe một lần · nhận dạng trên thiết bị…"
            activity.startVietnameseVoiceRecognition(handleVoiceResult)
        } else {
            voiceListening = false
            voiceStatus = "Bạn chưa cấp quyền micro. LocalPilot không thu âm."
        }
    }
    val startVoiceInput: () -> Unit = {
        when {
            Build.VERSION.SDK_INT < Build.VERSION_CODES.S -> {
                voiceStatus = "Nhận dạng tiếng Việt ngoại tuyến cần Android 12 trở lên."
            }
            activity == null -> voiceStatus = "Không thể mở micro lúc này."
            !SpeechRecognizer.isOnDeviceRecognitionAvailable(context) -> {
                voiceStatus = "Thiết bị chưa có nhận dạng ngoại tuyến; không dùng dịch vụ trực tuyến thay thế."
            }
            activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED -> {
                voiceListening = true
                voicePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
            else -> {
                voiceListening = true
                voiceStatus = "Đang nghe một lần · nhận dạng trên thiết bị…"
                activity.startVietnameseVoiceRecognition(handleVoiceResult)
            }
        }
    }

    Surface(color = Canvas, modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().imePadding()) {
            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 16.dp, bottom = 16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                item {
                    Header()
                    Spacer(Modifier.height(16.dp))
                    IntroCard()
                    Spacer(Modifier.height(12.dp))
                    SetupCard(
                        modelStatus = modelStatus,
                        modelReady = modelReady,
                        busy = busy,
                        onImport = { importLauncher.launch(arrayOf("*/*")) },
                        screenReady = screenReady,
                        onScreenSettings = openAccessibilitySettings,
                        shizukuStatus = shizukuStatus,
                        onShizukuGrant = { shizukuStatus = requestShizukuPermission() },
                        onShizukuCheck = { runShizukuCheck { result -> shizukuStatus = result } }
                    )
                    Spacer(Modifier.height(8.dp))
                    if (messages.isEmpty()) {
                        Text("BẮT ĐẦU", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
                        Spacer(Modifier.height(8.dp))
                        Text("Mô hình và nội dung trợ năng được xử lý trên điện thoại. Không có tài khoản hay máy chủ AI.", color = Muted, fontSize = 13.sp, lineHeight = 19.sp)
                    }
                }
                itemsIndexed(messages) { _, line -> ChatBubble(line) }
                if (busy) item {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = Color(0xFF587943))
                        Text("Đang suy luận trên máy…", color = Muted, fontSize = 13.sp)
                    }
                }
                if (screenPreview.isNotBlank()) item { ScreenSnapshotCard(screenPreview, screenPackage) }
                if (pendingActions.isNotEmpty()) item {
                    ActionCard(
                        actions = pendingActions,
                        targetPackage = pendingTargetPackage.orEmpty(),
                        onConfirm = {
                            val plan = pendingActions
                            val targetPackage = pendingTargetPackage
                            if (activity != null && ScreenAccessService.queueApprovedPlan(plan, targetPackage)) {
                                pendingActions = emptyList()
                                pendingTargetPackage = null
                                actionStatus = "Đã duyệt. Quay lại ứng dụng đích để chạy trong 30 giây."
                                activity.moveTaskToBack(true)
                            } else {
                                actionStatus = "Không thể xếp kế hoạch: bật Trợ năng, chụp lại màn hình app đích rồi thử lại."
                            }
                        },
                        onCancel = { pendingActions = emptyList(); pendingTargetPackage = null; actionStatus = "Đã hủy kế hoạch." }
                    )
                }
                if (actionStatus.isNotBlank() && pendingActions.isEmpty()) item {
                    Text(actionStatus, color = Muted, fontSize = 12.sp)
                }
            }

            Surface(color = Color.White, shadowElevation = 8.dp) {
                Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        OutlinedButton(
                            onClick = {
                                screenReady = accessibilityEnabled()
                                if (!screenReady) openAccessibilitySettings()
                                else if (ScreenAccessService.armNextScreenCapture()) {
                                    waitingForScreenCapture = true
                                    screenText = null
                                    screenPackage = null
                                    screenPreview = "Đã chờ chụp một lần. Chuyển sang ứng dụng cần đọc, đợi màn hình tải xong rồi quay lại LocalPilot."
                                } else {
                                    screenPreview = "Dịch vụ Trợ năng chưa sẵn sàng hoặc đang chụp lượt trước. Hãy thử lại sau giây lát."
                                }
                            },
                            enabled = !busy,
                            shape = RoundedCornerShape(14.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)
                        ) {
                            Icon(Icons.Default.Visibility, null, modifier = Modifier.size(17.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Chụp app khác", fontSize = 12.sp)
                        }
                        if (screenText != null) Text("Đã chụp văn bản app khác", color = Muted, fontSize = 11.sp, modifier = Modifier.align(Alignment.CenterVertically))
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(voiceStatus, color = Muted, fontSize = 10.sp, lineHeight = 14.sp)
                    Spacer(Modifier.height(5.dp))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        BasicTextField(
                            value = input,
                            onValueChange = { input = it },
                            modifier = Modifier.weight(1f).background(Color(0xFFF1F4F1), RoundedCornerShape(18.dp)).padding(horizontal = 16.dp, vertical = 14.dp),
                            textStyle = TextStyle(color = Ink, fontSize = 15.sp),
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                            keyboardActions = KeyboardActions(onSend = { sendMessage(null) }),
                            decorationBox = { inner ->
                                Box {
                                    if (input.isEmpty()) Text(if (modelReady) "Hỏi trợ lý trên máy…" else "Nạp mô hình để bắt đầu…", color = Muted, fontSize = 14.sp)
                                    inner()
                                }
                            }
                        )
                        OutlinedButton(
                            onClick = startVoiceInput,
                            enabled = modelReady && !busy && !voiceListening,
                            shape = CircleShape,
                            modifier = Modifier.size(48.dp),
                            contentPadding = PaddingValues(0.dp)
                        ) { Icon(Icons.Default.Mic, "Nói tiếng Việt", tint = Ink, modifier = Modifier.size(19.dp)) }
                        OutlinedButton(
                            onClick = {
                                activity?.cancelVietnameseVoiceRecognition()
                                voiceListening = false
                                val stopped = ScreenAccessService.cancelAutomation()
                                pendingActions = emptyList()
                                pendingTargetPackage = null
                                actionStatus = if (stopped) "Đã gửi lệnh dừng macro; bước đang thực hiện có thể hoàn tất." else "Không có macro nào đang chờ hoặc chạy."
                                voiceStatus = "Đã dừng theo yêu cầu."
                            },
                            shape = CircleShape,
                            modifier = Modifier.size(48.dp),
                            contentPadding = PaddingValues(0.dp)
                        ) { Icon(Icons.Default.StopCircle, "Dừng macro", tint = Color(0xFF9B3D32), modifier = Modifier.size(20.dp)) }
                        Button(
                            onClick = { sendMessage(null) },
                            enabled = modelReady && !busy && input.isNotBlank(),
                            shape = CircleShape,
                            modifier = Modifier.size(48.dp),
                            contentPadding = PaddingValues(0.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Ink)
                        ) { Icon(Icons.AutoMirrored.Filled.Send, "Gửi", tint = Color.White, modifier = Modifier.size(19.dp)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun Header() {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(42.dp).background(Ink, RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
            Icon(Icons.Default.SmartToy, contentDescription = null, tint = Green)
        }
        Spacer(Modifier.width(11.dp))
        Column(Modifier.weight(1f)) {
            Text("LocalPilot", color = Ink, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold)
            Text("TRỢ LÝ AI RIÊNG TƯ · ANDROID", color = Muted, fontSize = 9.sp, letterSpacing = 1.3.sp)
        }
        Surface(color = Color(0xFFE6F5DD), shape = CircleShape) {
            Text("● LOCAL", color = Color(0xFF426A2C), fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 11.dp, vertical = 7.dp))
        }
    }
}

@Composable
private fun IntroCard() {
    Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = Ink)) {
        Column(Modifier.fillMaxWidth().padding(20.dp)) {
            Surface(color = Color(0xFF29383A), shape = CircleShape) {
                Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Lock, null, tint = Green, modifier = Modifier.size(13.dp))
                    Spacer(Modifier.width(5.dp))
                    Text("THIẾT KẾ ƯU TIÊN RIÊNG TƯ", color = Green, fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = .8.sp)
                }
            }
            Spacer(Modifier.height(14.dp))
            Text("AI của bạn.\nChạy ngay trên máy.", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Bold, lineHeight = 30.sp)
            Spacer(Modifier.height(8.dp))
            Text("Nạp mô hình LLM tương thích, chủ động chia sẻ màn hình và xác nhận từng thao tác.", color = Color(0xFFC3CFCC), fontSize = 13.sp, lineHeight = 19.sp)
            Spacer(Modifier.height(15.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                Tag("KHÔNG GỬI DỮ LIỆU")
                Tag("BẠN LUÔN XÁC NHẬN")
            }
        }
    }
}

@Composable
private fun Tag(text: String) {
    Surface(color = Color(0xFF2B3939), shape = CircleShape) {
        Text(text, color = Color(0xFFDDE8E1), fontSize = 8.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(horizontal = 9.dp, vertical = 7.dp))
    }
}

@Composable
private fun SetupCard(
    modelStatus: String,
    modelReady: Boolean,
    busy: Boolean,
    onImport: () -> Unit,
    screenReady: Boolean,
    onScreenSettings: () -> Unit,
    shizukuStatus: String,
    onShizukuGrant: () -> Unit,
    onShizukuCheck: () -> Unit
) {
    Card(shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = Color.White), border = BorderStroke(1.dp, Border)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text("THIẾT LẬP", color = Muted, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.4.sp)
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (modelReady) Icons.Default.CheckCircle else Icons.Default.SmartToy, null, tint = if (modelReady) Color(0xFF4E8138) else Muted, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(9.dp))
                Column(Modifier.weight(1f)) {
                    Text("Mô hình AI trên máy", color = Ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    Text(modelStatus, color = Muted, fontSize = 11.sp, lineHeight = 15.sp)
                }
                TextButton(onClick = onImport, enabled = !busy) { Text("Chọn model", color = Color(0xFF466D32), fontSize = 12.sp) }
            }
            Spacer(Modifier.height(9.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Visibility, null, tint = if (screenReady) Color(0xFF4E8138) else Muted, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(9.dp))
                Column(Modifier.weight(1f)) {
                    Text("Đọc chữ trên màn hình", color = Ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    Text(if (screenReady) "Đã bật · chỉ đọc khi bạn yêu cầu" else "Tùy chọn · quyền Trợ năng Android", color = Muted, fontSize = 11.sp)
                }
                TextButton(onClick = onScreenSettings) { Text(if (screenReady) "Cài đặt" else "Bật", color = Color(0xFF466D32), fontSize = 12.sp) }
            }
            Spacer(Modifier.height(9.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.PhoneAndroid, null, tint = Muted, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(9.dp))
                Column(Modifier.weight(1f)) {
                    Text("Shizuku (tùy chọn)", color = Ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    Text(shizukuStatus, color = Muted, fontSize = 10.sp, lineHeight = 14.sp)
                }
                TextButton(onClick = onShizukuGrant) { Text("Cấp quyền", color = Color(0xFF466D32), fontSize = 11.sp) }
            }
            OutlinedButton(onClick = onShizukuCheck, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)) {
                Text("Kiểm tra kết nối Shizuku · chỉ đọc", fontSize = 12.sp, color = Ink)
            }
        }
    }
}

@Composable
private fun ChatBubble(line: ChatLine) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (line.fromUser) Arrangement.End else Arrangement.Start) {
        Surface(
            color = if (line.fromUser) Ink else Color.White,
            shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomEnd = if (line.fromUser) 5.dp else 18.dp, bottomStart = if (line.fromUser) 18.dp else 5.dp),
            border = if (line.fromUser) null else BorderStroke(1.dp, Border),
            modifier = Modifier.fillMaxWidth(.88f)
        ) {
            Text(line.text, color = if (line.fromUser) Color.White else Ink, fontSize = 14.sp, lineHeight = 21.sp, modifier = Modifier.padding(horizontal = 15.dp, vertical = 12.dp))
        }
    }
}

@Composable
private fun ScreenSnapshotCard(text: String, packageName: String?) {
    Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFFEAF1E9))) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            Text("APP ĐÍCH: ${packageName ?: "không rõ"} · VĂN BẢN TẠM THỜI", color = Color(0xFF45633D), fontSize = 9.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text(text, color = Ink, fontSize = 12.sp, lineHeight = 17.sp)
        }
    }
}

@Composable
private fun ActionCard(actions: List<UiAction>, targetPackage: String, onConfirm: () -> Unit, onCancel: () -> Unit) {
    Card(shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF7E7)), border = BorderStroke(1.dp, Color(0xFFF0D8A9))) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            Text("DUYỆT KẾ HOẠCH · ${actions.size} BƯỚC", color = Color(0xFF76531A), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
            Text("Chỉ chạy trong app: $targetPackage", color = Muted, fontSize = 10.sp, modifier = Modifier.padding(top = 4.dp))
            Spacer(Modifier.height(6.dp))
            actions.forEachIndexed { index, action ->
                when (action) {
                    is UiAction.Tap -> Text("${index + 1}. Chạm nhãn “${action.label}”", color = Ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(vertical = 3.dp))
                    is UiAction.Type -> Column(Modifier.padding(vertical = 3.dp)) {
                        Text("${index + 1}. Thay nội dung ô “${action.label}” bằng:", color = Ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        Text("“${action.text}”", color = Color(0xFF45633D), fontSize = 12.sp, lineHeight = 17.sp)
                    }
                }
            }
            Text("Chỉ chạy sau khi bạn duyệt. Không gửi biểu mẫu/tin nhắn; không nhập mật khẩu hay mã xác thực.", color = Muted, fontSize = 11.sp, lineHeight = 15.sp, modifier = Modifier.padding(top = 6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 10.dp)) {
                Button(onClick = onConfirm, shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = Ink)) {
                    Text("Duyệt & quay lại app", color = Color.White)
                }
                TextButton(onClick = onCancel) { Text("Hủy", color = Muted) }
            }
        }
    }
}

private fun isStopVoiceCommand(text: String): Boolean {
    val command = text.lowercase().trim().trimEnd('.', '!', '?', ',', ';', ':').replace(Regex("\\s+"), " ")
    return command in setOf(
        "dừng", "dừng lại", "dừng bot", "dừng macro", "dừng thao tác", "dừng kế hoạch", "dừng lại ngay",
        "hãy dừng", "hãy dừng lại", "hủy", "huỷ", "hủy macro", "huỷ macro", "hủy thao tác", "huỷ thao tác",
        "hủy kế hoạch", "huỷ kế hoạch", "đừng làm nữa", "stop", "stop macro"
    )
}

private fun parseActionPlan(planLine: String, screenText: String, userRequest: String): List<UiAction> {
    return try {
        val json = planLine.substringAfter("ACTION_PLAN_JSON:").trim().trim('`')
        val items = JSONArray(json)
        if (items.length() !in 1..5) return emptyList()
        val visibleLines = screenText.lineSequence().map { it.trim() }.toSet()
        val plan = ArrayList<UiAction>(items.length())
        var typedChars = 0
        for (i in 0 until items.length()) {
            val item = items.getJSONObject(i)
            val label = item.optString("label").trim()
            if (label.length !in 2..120) return emptyList()
            when (item.optString("type").lowercase()) {
                "tap" -> {
                    if (label !in visibleLines || BLOCKED_ACTION_WORDS.any { label.contains(it, ignoreCase = true) }) return emptyList()
                    plan += UiAction.Tap(label)
                }
                "type" -> {
                    val value = item.optString("text")
                    if ("INPUT: $label" !in visibleLines || value.isBlank() || value.length > 500 ||
                        !userRequest.contains(value, ignoreCase = true) || isSensitiveField(label)) return emptyList()
                    typedChars += value.length
                    if (typedChars > 1_000) return emptyList()
                    plan += UiAction.Type(label, value)
                }
                else -> return emptyList()
            }
        }
        plan
    } catch (_: Exception) {
        emptyList()
    }
}

private fun isSensitiveField(label: String): Boolean {
    val lower = label.lowercase()
    if (listOf("mật khẩu", "mã xác thực", "mã otp", "thẻ ngân hàng").any { lower.contains(it) }) return true
    val tokens = lower.split(Regex("[^\\p{L}\\p{N}]+"))
    return tokens.any { it in setOf("password", "passcode", "otp", "pin", "cvv", "verification") }
}

private val ACTION_INTENT_WORDS = listOf(
    "tap", "click", "open", "select", "type", "enter", "write", "fill", "macro", "search",
    "chạm", "bấm", "nhấn", "mở", "chọn", "nhập", "gõ", "điền", "soạn", "tìm"
)
private val BLOCKED_ACTION_WORDS = listOf(
    "pay", "purchase", "buy", "delete", "remove", "send", "post", "submit", "transfer", "confirm", "approve",
    "thanh toán", "mua", "xóa", "xoá", "gửi", "đăng", "nộp", "chuyển tiền", "xác nhận", "phê duyệt", "đồng ý"
)
