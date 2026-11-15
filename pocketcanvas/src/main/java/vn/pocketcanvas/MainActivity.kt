package vn.pocketcanvas

import android.app.Activity
import android.content.Intent
import android.content.ClipData
import android.content.ClipboardManager
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.util.Log
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.Executors
import kotlin.random.Random

/** Small, offline text-to-image app. The model is imported by the user; no weights are bundled. */
class MainActivity : Activity() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor { runnable -> Thread(runnable, "pocketcanvas-inference") }
    private var generatedBitmap: Bitmap? = null
    private var modelDirectory: File? = null
    private lateinit var modelStatus: TextView
    private lateinit var apiStatusText: TextView
    private lateinit var apiDetailsText: TextView
    private lateinit var apiButton: Button
    private lateinit var promptInput: EditText
    private lateinit var stepsLabel: TextView
    private lateinit var progress: ProgressBar
    private lateinit var statusText: TextView
    private lateinit var generateButton: Button
    private lateinit var saveButton: Button
    private lateinit var outputImage: ImageView
    private var steps = 10

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(244, 242, 250)
        window.navigationBarColor = Color.rgb(244, 242, 250)
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        buildUi()
        LocalImageApiService.statusListener = { message ->
            runOnUiThread {
                showStatus(message)
                if (::apiStatusText.isInitialized) apiStatusText.text = message
                if (message.startsWith("Không bật được API") || message == "Local API đã tắt.") {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(API_ENABLED, false).apply()
                    updateApiUi(false)
                }
            }
        }
        findInstalledModel()
        updateApiUi(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(API_ENABLED, false))
    }

    override fun onResume() {
        super.onResume()
        if (::apiButton.isInitialized) updateApiUi(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(API_ENABLED, false))
    }

    override fun onDestroy() {
        LocalImageApiService.statusListener = null
        worker.shutdown()
        super.onDestroy()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK || data?.data == null) return
        when (requestCode) {
            REQUEST_IMPORT -> importModelZip(data.data!!)
            REQUEST_SAVE -> saveGeneratedImage(data.data!!)
        }
    }

    private fun buildUi() {
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(24))
        }
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            fitsSystemWindows = true
            setBackgroundColor(Color.rgb(244, 242, 250))
            addView(page)
        }
        page.addView(TextView(this).apply {
            text = "✦  POCKETCANVAS"
            textSize = 13f
            letterSpacing = 0.12f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.rgb(105, 77, 219))
        }, margin(bottom = 10))
        page.addView(TextView(this).apply {
            text = "Vẽ ảnh ngay trên máy"
            textSize = 28f
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
            setTextColor(Color.rgb(29, 27, 39))
        }, margin(bottom = 6))
        page.addView(TextView(this).apply {
            text = "Tạo ảnh offline bằng Stable Diffusion 1.5 + MediaPipe. Prompt và ảnh không rời khỏi điện thoại."
            textSize = 14f
            setTextColor(Color.rgb(104, 101, 119))
            setLineSpacing(dp(3).toFloat(), 1f)
        }, margin(bottom = 16))

        val modelCard = card()
        modelCard.addView(label("MODEL CỤC BỘ"), margin(bottom = 6))
        modelStatus = TextView(this).apply {
            text = "Chưa cài model. Cần nhập gói Stable Diffusion 1.5 tương thích MediaPipe."
            textSize = 13f
            setTextColor(Color.rgb(82, 78, 99))
            setLineSpacing(dp(2).toFloat(), 1f)
        }
        modelCard.addView(modelStatus, margin(bottom = 10))
        val modelActions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        modelActions.addView(secondaryButton("Nhập gói .zip") { chooseModelZip() }, LinearLayout.LayoutParams(0, dp(44), 1f))
        modelActions.addView(View(this), LinearLayout.LayoutParams(dp(8), 1))
        modelActions.addView(secondaryButton("Tải model") { openModelPage() }, LinearLayout.LayoutParams(0, dp(44), 1f))
        modelCard.addView(modelActions)
        page.addView(modelCard, margin(bottom = 12))

        val apiCard = card()
        apiCard.addView(label("DÙNG MODEL TRONG LOCALMIND"), margin(bottom = 6))
        apiCard.addView(TextView(this).apply {
            text = "Bật endpoint ảnh cục bộ, sau đó thêm PocketCanvas vào LocalMind dưới dạng OpenAI-compatible server."
            textSize = 13f
            setTextColor(Color.rgb(92, 87, 109))
            setLineSpacing(dp(2).toFloat(), 1f)
        }, margin(bottom = 8))
        apiStatusText = TextView(this).apply {
            text = "API đang tắt. Cài model trước khi bật."
            textSize = 12f
            setTextColor(Color.rgb(112, 106, 130))
        }
        apiCard.addView(apiStatusText, margin(bottom = 7))
        apiDetailsText = TextView(this).apply {
            textSize = 12f
            setTextColor(Color.rgb(61, 57, 77))
            setTextIsSelectable(true)
            visibility = View.GONE
            setPadding(dp(10), dp(8), dp(10), dp(8))
            background = rounded(Color.rgb(247, 246, 251), dp(10), Color.rgb(231, 227, 240), dp(1))
        }
        apiCard.addView(apiDetailsText, margin(bottom = 8))
        val apiActions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        apiButton = primaryButton("Bật API cho LocalMind").apply {
            isEnabled = false
            alpha = 0.5f
            setOnClickListener { toggleLocalApi() }
        }
        apiActions.addView(apiButton, LinearLayout.LayoutParams(0, dp(46), 1f))
        apiActions.addView(View(this), LinearLayout.LayoutParams(dp(8), 1))
        apiActions.addView(secondaryButton("Sao chép API key") { copyLocalMindConfig() }, LinearLayout.LayoutParams(0, dp(46), 1f))
        apiCard.addView(apiActions)
        page.addView(apiCard, margin(bottom = 17))

        page.addView(label("MÔ TẢ BỨC ẢNH"), margin(bottom = 7))
        promptInput = EditText(this).apply {
            hint = "Ví dụ: một chú mèo phi hành gia trên mặt trăng, tranh minh họa màu nước"
            textSize = 15f
            minLines = 3
            maxLines = 5
            gravity = Gravity.TOP or Gravity.START
            setPadding(dp(14), dp(13), dp(14), dp(13))
            setTextColor(Color.rgb(35, 31, 49))
            setHintTextColor(Color.rgb(151, 146, 166))
            background = rounded(Color.WHITE, dp(14), Color.rgb(226, 222, 238), dp(1))
        }
        page.addView(promptInput, margin(bottom = 12))

        val stepsRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        stepsRow.addView(label("SỐ BƯỚC"), LinearLayout.LayoutParams(0, -2, 1f))
        stepsLabel = TextView(this).apply { text = "$steps"; textSize = 14f; typeface = Typeface.DEFAULT_BOLD; setTextColor(Color.rgb(105, 77, 219)) }
        stepsRow.addView(stepsLabel)
        page.addView(stepsRow, margin(bottom = 2))
        val seek = SeekBar(this).apply {
            min = 5
            max = 20
            progress = steps - 5
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progressValue: Int, fromUser: Boolean) {
                    steps = progressValue + 5
                    stepsLabel.text = steps.toString()
                }
                override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
            })
        }
        page.addView(seek, margin(bottom = 10))
        page.addView(TextView(this).apply {
            text = "4 GB RAM: thử 5–10 bước trước, đóng ứng dụng khác và để máy mát. Ảnh sinh có thể chậm hoặc vượt bộ nhớ tùy điện thoại."
            textSize = 12f
            setTextColor(Color.rgb(119, 114, 135))
            setLineSpacing(dp(2).toFloat(), 1f)
        }, margin(bottom = 12))

        generateButton = primaryButton("Tạo ảnh offline").apply {
            isEnabled = false
            alpha = 0.5f
            setOnClickListener { generateImage() }
        }
        page.addView(generateButton, margin(bottom = 9))
        progress = ProgressBar(this).apply { visibility = View.GONE; isIndeterminate = true }
        page.addView(progress, margin(bottom = 8))

        outputImage = ImageView(this).apply {
            visibility = View.GONE
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
            background = rounded(Color.WHITE, dp(14), Color.rgb(226, 222, 238), dp(1))
        }
        page.addView(outputImage, margin(bottom = 10))
        saveButton = secondaryButton("Lưu ảnh PNG") { requestSave() }.apply { visibility = View.GONE }
        page.addView(saveButton, margin(bottom = 12))
        statusText = TextView(this).apply {
            text = "Sẵn sàng. Cài model để bắt đầu tạo ảnh."
            textSize = 13f
            setTextColor(Color.rgb(102, 97, 119))
            setLineSpacing(dp(2).toFloat(), 1f)
        }
        page.addView(statusText)

        setContentView(scroll)
    }

    private fun findInstalledModel() {
        val savedPath = getSharedPreferences(PREFS, MODE_PRIVATE).getString(MODEL_PATH, null)
        val saved = savedPath?.let(::File)
        val valid = saved?.takeIf(ModelPackage::isValid)
        if (valid != null) setModelReady(valid)
    }

    private fun chooseModelZip() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "application/zip"
            putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("application/zip", "application/x-zip-compressed", "application/octet-stream"))
        }
        try { startActivityForResult(intent, REQUEST_IMPORT) } catch (_: Exception) {
            Toast.makeText(this, "Không mở được bộ chọn tệp.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun importModelZip(uri: Uri) {
        if (getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(API_ENABLED, false)) {
            showStatus("Hãy tắt LocalMind API trước khi thay model.")
            return
        }
        val displayName = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }.orEmpty()
        if (displayName.isNotBlank() && !displayName.endsWith(".zip", ignoreCase = true)) {
            showStatus("Hãy chọn file .zip model MediaPipe, không phải file GGUF.")
            return
        }
        setBusy(true, "Đang giải nén gói model vào bộ nhớ riêng của ứng dụng…")
        worker.execute {
            val temp = File(filesDir, "model-importing")
            val finalDir = File(filesDir, "models/sd15-mediapipe")
            try {
                temp.deleteRecursively()
                temp.mkdirs()
                var total = 0L
                contentResolver.openInputStream(uri)?.use { raw ->
                    java.util.zip.ZipInputStream(BufferedInputStream(raw)).use { zip ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val entry = zip.nextEntry ?: break
                            val out = File(temp, entry.name)
                            val rootPath = temp.canonicalPath + File.separator
                            if (!out.canonicalPath.startsWith(rootPath) && out.canonicalPath != temp.canonicalPath) {
                                throw IllegalArgumentException("Gói ZIP có đường dẫn không an toàn.")
                            }
                            if (entry.isDirectory) {
                                out.mkdirs()
                            } else {
                                out.parentFile?.mkdirs()
                                FileOutputStream(out).buffered().use { stream ->
                                    while (true) {
                                        val count = zip.read(buffer)
                                        if (count <= 0) break
                                        total += count
                                        if (total > MAX_UNPACKED_BYTES) throw IllegalArgumentException("Gói model vượt giới hạn dung lượng 5 GB.")
                                        stream.write(buffer, 0, count)
                                    }
                                }
                            }
                            zip.closeEntry()
                        }
                    }
                } ?: throw IllegalArgumentException("Không đọc được file ZIP đã chọn.")

                val modelRoot = ModelPackage.findRoot(temp)
                    ?: throw IllegalArgumentException("Không thấy vocab và các tensor .bin trong ZIP. Hãy tải gói sd15-mediapipe, không phải GGUF.")
                finalDir.deleteRecursively()
                finalDir.parentFile?.mkdirs()
                if (!modelRoot.renameTo(finalDir)) copyFolder(modelRoot, finalDir)
                temp.deleteRecursively()
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(MODEL_PATH, finalDir.absolutePath).apply()
                mainHandler.post { setModelReady(finalDir) }
            } catch (error: Exception) {
                temp.deleteRecursively()
                mainHandler.post {
                    setBusy(false)
                    showStatus("Không nhập được model: ${error.message ?: "file không hợp lệ"}")
                }
            }
        }
    }

    private fun generateImage() {
        val prompt = promptInput.text?.toString()?.trim().orEmpty()
        val model = modelDirectory
        if (prompt.isBlank()) {
            showStatus("Hãy nhập mô tả ảnh trước.")
            return
        }
        if (model == null || !ModelPackage.isValid(model)) {
            showStatus("Cài gói model tương thích trước khi tạo ảnh.")
            return
        }
        setBusy(true, "Đang nạp model cục bộ… giữ ứng dụng mở trong lúc chạy.")
        val seed = Random.nextInt(0, Int.MAX_VALUE)
        val currentSteps = steps
        worker.execute {
            try {
                mainHandler.post { showStatus("Đang tạo ảnh offline · $currentSteps bước · seed $seed …") }
                val bitmap = DiffusionRuntime.generateBitmap(this, model, prompt, currentSteps, seed)
                mainHandler.post {
                    generatedBitmap = bitmap
                    outputImage.setImageBitmap(bitmap)
                    outputImage.visibility = View.VISIBLE
                    saveButton.visibility = View.VISIBLE
                    setBusy(false)
                    showStatus("Ảnh đã tạo trên điện thoại. Seed: $seed")
                }
            } catch (error: Exception) {
                Log.e("PocketCanvas", "Local image generation failed", error)
                mainHandler.post {
                    setBusy(false)
                    showStatus(ImageGenErrorMessages.explain(error))
                }
            }
        }
    }

    private fun requestSave() {
        if (generatedBitmap == null) return
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "image/png"
            putExtra(Intent.EXTRA_TITLE, "pocketcanvas-${System.currentTimeMillis()}.png")
        }
        try { startActivityForResult(intent, REQUEST_SAVE) } catch (_: Exception) {
            Toast.makeText(this, "Không mở được nơi lưu ảnh.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun saveGeneratedImage(uri: Uri) {
        val bitmap = generatedBitmap ?: return
        setBusy(true, "Đang lưu ảnh…")
        worker.execute {
            try {
                contentResolver.openOutputStream(uri)?.use { output ->
                    if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) throw IllegalStateException("Không mã hóa được ảnh PNG.")
                } ?: throw IllegalStateException("Không ghi được tệp đích.")
                mainHandler.post { setBusy(false); showStatus("Đã lưu ảnh PNG.") }
            } catch (error: Exception) {
                mainHandler.post { setBusy(false); showStatus("Lưu ảnh thất bại: ${error.message}") }
            }
        }
    }

    private fun openModelPage() {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://huggingface.co/cuesetac/sd15-mediapipe")))
        } catch (_: Exception) {
            showStatus("Không mở được trang model. Tìm repository cuesetac/sd15-mediapipe.")
        }
    }

    private fun toggleLocalApi() {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val enabled = prefs.getBoolean(API_ENABLED, false)
        if (enabled) {
            stopService(Intent(this, LocalImageApiService::class.java))
            prefs.edit().putBoolean(API_ENABLED, false).apply()
            updateApiUi(false)
            showStatus("Đã gửi yêu cầu tắt LocalMind API.")
            return
        }
        val model = modelDirectory
        if (model == null || !ModelPackage.isValid(model)) {
            showStatus("Nhập model hợp lệ trước khi bật API cho LocalMind.")
            return
        }
        val token = getOrCreateApiToken()
        val intent = Intent(this, LocalImageApiService::class.java)
            .putExtra(LocalImageApiService.EXTRA_MODEL_PATH, model.absolutePath)
            .putExtra(LocalImageApiService.EXTRA_TOKEN, token)
        try {
            startForegroundService(intent)
            prefs.edit().putBoolean(API_ENABLED, true).apply()
            updateApiUi(true)
            showStatus("Đang bật endpoint cục bộ…")
        } catch (error: Exception) {
            prefs.edit().putBoolean(API_ENABLED, false).apply()
            updateApiUi(false)
            showStatus("Không bật được local API: ${error.message ?: "kiểm tra quyền thông báo/dịch vụ"}")
        }
    }

    private fun getOrCreateApiToken(): String {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        prefs.getString(API_TOKEN, null)?.let { return it }
        val bytes = ByteArray(24).also { java.security.SecureRandom().nextBytes(it) }
        val token = android.util.Base64.encodeToString(
            bytes,
            android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP or android.util.Base64.NO_PADDING
        )
        prefs.edit().putString(API_TOKEN, token).apply()
        return token
    }

    private fun updateApiUi(enabled: Boolean) {
        if (!::apiButton.isInitialized || !::apiStatusText.isInitialized || !::apiDetailsText.isInitialized) return
        val token = getOrCreateApiToken()
        apiButton.text = if (enabled) "Tắt API LocalMind" else "Bật API cho LocalMind"
        apiButton.isEnabled = modelDirectory != null
        apiButton.alpha = if (apiButton.isEnabled) 1f else 0.5f
        apiStatusText.text = if (enabled) LocalImageApiService.currentStatus else "API đang tắt. Chỉ lắng nghe trên 127.0.0.1."
        apiDetailsText.text = "Loại server: OpenAI-compatible\nHost: 127.0.0.1\nPort: ${LocalImageApiServer.PORT}\nAPI path: /v1\nImage model ID: ${LocalImageApiServer.MODEL_ID}\nAPI key: $token"
        apiDetailsText.visibility = if (enabled) View.VISIBLE else View.GONE
    }

    private fun copyLocalMindConfig() {
        val token = getOrCreateApiToken()
        val clipboard = getSystemService(ClipboardManager::class.java)
        clipboard.setPrimaryClip(ClipData.newPlainText("PocketCanvas API key", token))
        showStatus("Đã sao chép API key. Dán vào server OpenAI-compatible trong LocalMind.")
    }

    private fun setModelReady(directory: File) {
        modelDirectory = directory
        modelStatus.text = "Đã cài model MediaPipe. Lần chạy đầu sẽ nạp trọng số; cần đủ dung lượng trống."
        modelStatus.setTextColor(Color.rgb(44, 127, 88))
        generateButton.isEnabled = true
        generateButton.alpha = 1f
        updateApiUi(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(API_ENABLED, false))
        showStatus("Model đã sẵn sàng. Có thể sinh ảnh tại đây hoặc mở API cho LocalMind.")
    }

    private fun setBusy(busy: Boolean, message: String? = null) {
        progress.visibility = if (busy) View.VISIBLE else View.GONE
        generateButton.isEnabled = !busy && modelDirectory != null
        generateButton.alpha = if (generateButton.isEnabled) 1f else 0.5f
        if (message != null) showStatus(message)
    }

    private fun showStatus(message: String) {
        if (::statusText.isInitialized) statusText.text = message
    }

    private fun copyFolder(source: File, destination: File) {
        if (source.isDirectory) {
            destination.mkdirs()
            source.listFiles()?.forEach { child -> copyFolder(child, File(destination, child.name)) }
        } else {
            source.inputStream().buffered().use { input ->
                BufferedOutputStream(FileOutputStream(destination)).use { output -> input.copyTo(output) }
            }
        }
    }

    private fun label(text: String) = TextView(this).apply {
        this.text = text
        textSize = 11f
        letterSpacing = 0.1f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.rgb(127, 121, 146))
    }

    private fun card() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(14), dp(13), dp(14), dp(13))
        background = rounded(Color.WHITE, dp(16), Color.rgb(230, 226, 240), dp(1))
    }

    private fun primaryButton(text: String) = Button(this).apply {
        this.text = text
        isAllCaps = false
        textSize = 15f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.WHITE)
        background = rounded(Color.rgb(105, 77, 219), dp(13), null, 0)
        backgroundTintList = null
        minHeight = dp(50)
        stateListAnimator = null
    }

    private fun secondaryButton(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        isAllCaps = false
        textSize = 13f
        setTextColor(Color.rgb(93, 67, 192))
        background = rounded(Color.WHITE, dp(12), Color.rgb(226, 222, 238), dp(1))
        backgroundTintList = null
        stateListAnimator = null
        setOnClickListener { onClick() }
    }

    private fun rounded(fill: Int, radius: Int, stroke: Int?, strokeWidth: Int) = GradientDrawable().apply {
        setColor(fill)
        cornerRadius = radius.toFloat()
        if (stroke != null) setStroke(strokeWidth, stroke)
    }

    private fun margin(bottom: Int = 0, top: Int = 0): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            this.bottomMargin = dp(bottom)
            this.topMargin = dp(top)
        }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val PREFS = "pocketcanvas"
        private const val MODEL_PATH = "model_path"
        private const val API_ENABLED = "localmind_api_enabled"
        private const val API_TOKEN = "localmind_api_token"
        private const val REQUEST_IMPORT = 1001
        private const val REQUEST_SAVE = 1002
        private const val MAX_UNPACKED_BYTES = 5L * 1024 * 1024 * 1024
    }
}

internal object ModelPackage {
    fun isValid(directory: File): Boolean = findRoot(directory) != null

    fun findRoot(start: File): File? {
        fun search(directory: File, depth: Int): File? {
            if (!directory.isDirectory || depth > 5) return null
            val files = directory.listFiles() ?: return null
            val hasVocab = files.any { it.isFile && it.name.equals("bpe_simple_vocab_16e6.txt", true) }
            val hasWeights = files.any { it.isFile && it.extension.equals("bin", true) }
            if (hasVocab && hasWeights) return directory
            files.filter { it.isDirectory }.forEach { child -> search(child, depth + 1)?.let { return it } }
            return null
        }
        return search(start, 0)
    }
}
