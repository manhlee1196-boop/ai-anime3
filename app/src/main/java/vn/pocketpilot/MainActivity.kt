package vn.pocketpilot

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable

class MainActivity : Activity() {
    private lateinit var prompt: EditText
    private lateinit var permissionText: TextView
    private lateinit var statusText: TextView
    private lateinit var previewPanel: LinearLayout
    private lateinit var previewSteps: LinearLayout
    private lateinit var runButton: Button
    private lateinit var stopButton: Button
    private var currentPlan: TaskPlan? = null
    private var currentCommand = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(245, 246, 250)
        window.navigationBarColor = Color.rgb(245, 246, 250)
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        buildScreen()
        PhoneAutomationService.statusListener = { message -> runOnUiThread { showStatus(message) } }
        updatePermissionState()
    }

    override fun onResume() {
        super.onResume()
        if (::permissionText.isInitialized) updatePermissionState()
        if (::statusText.isInitialized && PhoneAutomationService.instance == null) {
            val last = getSharedPreferences(PhoneAutomationService.PREFS, MODE_PRIVATE)
                .getString(PhoneAutomationService.LAST_STATUS, null)
            if (!last.isNullOrBlank()) showStatus(last)
        }
    }

    override fun onDestroy() {
        if (PhoneAutomationService.statusListener != null) PhoneAutomationService.statusListener = null
        super.onDestroy()
    }

    private fun buildScreen() {
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            fitsSystemWindows = true
            setBackgroundColor(Color.rgb(245, 246, 250))
        }
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(20), dp(22), dp(28))
        }
        scroll.addView(page)

        val brand = TextView(this).apply {
            text = "✦  POCKETPILOT"
            textSize = 13f
            letterSpacing = 0.12f
            setTextColor(Color.rgb(99, 91, 255))
            typeface = Typeface.DEFAULT_BOLD
        }
        page.addView(brand, margin(bottom = 14))
        page.addView(TextView(this).apply {
            text = "Trợ lý tự động\ncho điện thoại của bạn"
            textSize = 30f
            setTextColor(Color.rgb(25, 29, 45))
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
            setLineSpacing(dp(1).toFloat(), 1f)
        }, margin(bottom = 10))
        page.addView(TextView(this).apply {
            text = "Mô tả việc cần làm. PocketPilot sẽ lập kế hoạch trên máy và chỉ chạy sau khi bạn xác nhận."
            textSize = 15f
            setTextColor(Color.rgb(101, 108, 126))
            setLineSpacing(dp(3).toFloat(), 1f)
        }, margin(bottom = 20))

        val accessCard = card()
        val accessHead = row()
        accessHead.addView(TextView(this).apply { text = "◉"; textSize = 21f; setTextColor(Color.rgb(99, 91, 255)) }, LinearLayout.LayoutParams(dp(34), -2))
        val accessCopy = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        accessCopy.addView(TextView(this).apply { text = "Quyền tự động hóa"; textSize = 15f; setTextColor(Color.rgb(32, 36, 52)); typeface = Typeface.DEFAULT_BOLD })
        permissionText = TextView(this).apply { textSize = 13f; setTextColor(Color.rgb(101, 108, 126)); text = "Đang kiểm tra quyền…" }
        accessCopy.addView(permissionText, margin(top = 3))
        accessHead.addView(accessCopy, LinearLayout.LayoutParams(0, -2, 1f))
        val permissionButton = Button(this).apply {
            text = "Thiết lập"
            isAllCaps = false
            textSize = 13f
            setTextColor(Color.rgb(73, 65, 215))
            setPadding(dp(8), 0, dp(8), 0)
            setOnClickListener { openAccessibilitySettings() }
        }
        accessHead.addView(permissionButton, LinearLayout.LayoutParams(-2, dp(42)))
        accessCard.addView(accessHead)
        page.addView(accessCard, margin(bottom = 22))

        page.addView(label("YÊU CẦU CỦA BẠN"), margin(bottom = 8))
        prompt = EditText(this).apply {
            hint = "Ví dụ: Mở YouTube và tìm nhạc thư giãn"
            textSize = 16f
            gravity = Gravity.TOP or Gravity.START
            minLines = 3
            maxLines = 5
            setPadding(dp(15), dp(14), dp(15), dp(14))
            setTextColor(Color.rgb(32, 36, 52))
            setHintTextColor(Color.rgb(153, 159, 174))
            background = rounded(Color.WHITE, dp(15), Color.rgb(225, 228, 237), dp(1))
        }
        page.addView(prompt, margin(bottom = 12))
        val analyze = primaryButton("Lập kế hoạch")
        analyze.setOnClickListener { createPreview() }
        page.addView(analyze, margin(bottom = 13))

        page.addView(label("THỬ NHANH"), margin(bottom = 8))
        val quickRow = row()
        quickRow.addView(secondaryButton("Mở YouTube") { useExample("Mở YouTube") }, LinearLayout.LayoutParams(0, dp(42), 1f))
        quickRow.addView(View(this), LinearLayout.LayoutParams(dp(8), 1))
        quickRow.addView(secondaryButton("Cuộn xuống") { useExample("Cuộn xuống") }, LinearLayout.LayoutParams(0, dp(42), 1f))
        page.addView(quickRow, margin(bottom = 18))

        previewPanel = card().apply { visibility = View.GONE }
        previewPanel.addView(label("KẾ HOẠCH THAO TÁC"), margin(bottom = 10))
        previewSteps = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        previewPanel.addView(previewSteps)
        val safety = TextView(this).apply {
            text = "Bạn có thể dừng bất cứ lúc nào. Tác vụ nhạy cảm như gửi tin, thanh toán và xóa dữ liệu không được tự động thực hiện."
            textSize = 12f
            setTextColor(Color.rgb(101, 108, 126))
            setLineSpacing(dp(2).toFloat(), 1f)
        }
        previewPanel.addView(safety, margin(top = 12, bottom = 12))
        runButton = primaryButton("Chạy tác vụ đã xem")
        runButton.setOnClickListener { runCurrentTask() }
        previewPanel.addView(runButton)
        stopButton = secondaryButton("Dừng tác vụ") {
            val service = PhoneAutomationService.instance
            if (service != null) service.stopTask() else showStatus("Không có tác vụ đang chạy.")
        }
        previewPanel.addView(stopButton, margin(top = 7))
        page.addView(previewPanel, margin(bottom = 18))

        val statusCard = card()
        statusCard.addView(label("TRẠNG THÁI"), margin(bottom = 6))
        statusText = TextView(this).apply {
            text = "Sẵn sàng. Tác vụ được phân tích trực tiếp trên thiết bị."
            textSize = 14f
            setTextColor(Color.rgb(71, 78, 99))
            setLineSpacing(dp(2).toFloat(), 1f)
        }
        statusCard.addView(statusText)
        page.addView(statusCard)

        setContentView(scroll)
    }

    private fun createPreview() {
        val command = prompt.text?.toString().orEmpty().trim()
        val plan = TaskPlanner.plan(this, command)
        currentCommand = command
        currentPlan = plan
        previewSteps.removeAllViews()
        previewPanel.visibility = View.VISIBLE
        if (plan.error != null) {
            previewSteps.addView(TextView(this).apply {
                text = plan.error
                textSize = 14f
                setTextColor(Color.rgb(168, 73, 39))
                setLineSpacing(dp(3).toFloat(), 1f)
            })
            runButton.isEnabled = false
            runButton.alpha = 0.45f
        } else {
            plan.steps.forEachIndexed { index, step ->
                val item = row()
                item.addView(TextView(this).apply {
                    text = "${index + 1}"
                    gravity = Gravity.CENTER
                    textSize = 13f
                    typeface = Typeface.DEFAULT_BOLD
                    setTextColor(Color.rgb(73, 65, 215))
                    background = rounded(Color.rgb(239, 238, 255), dp(20), null, 0)
                }, LinearLayout.LayoutParams(dp(27), dp(27)))
                val details = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(10), 0, 0, 0) }
                details.addView(TextView(this).apply {
                    text = step.description
                    textSize = 14f
                    setTextColor(Color.rgb(40, 45, 62))
                    typeface = Typeface.DEFAULT_BOLD
                })
                item.addView(details, LinearLayout.LayoutParams(0, -2, 1f))
                previewSteps.addView(item, margin(bottom = 9))
            }
            runButton.isEnabled = true
            runButton.alpha = 1f
            showStatus("Đã lập kế hoạch gồm ${plan.steps.size} thao tác. Xem lại rồi nhấn chạy.")
        }
    }

    private fun runCurrentTask() {
        val plan = currentPlan ?: return
        if (plan.error != null || plan.steps.isEmpty()) return
        if (!isAccessibilityEnabled()) {
            getSharedPreferences(PhoneAutomationService.PREFS, MODE_PRIVATE).edit()
                .putString(PhoneAutomationService.PENDING_COMMAND, currentCommand).apply()
            showStatus("Bật quyền Trợ năng của PocketPilot để tiếp tục. Sau khi bật, tác vụ đã xác nhận sẽ chạy.")
            openAccessibilitySettings()
            return
        }
        val service = PhoneAutomationService.instance
        if (service == null) {
            getSharedPreferences(PhoneAutomationService.PREFS, MODE_PRIVATE).edit()
                .putString(PhoneAutomationService.PENDING_COMMAND, currentCommand).apply()
            showStatus("Đang kết nối dịch vụ tự động hóa…")
            return
        }
        service.runCommand(currentCommand)
    }

    private fun useExample(text: String) {
        prompt.setText(text)
        createPreview()
    }

    private fun updatePermissionState() {
        val enabled = isAccessibilityEnabled()
        permissionText.text = if (enabled) "Đã bật — sẵn sàng thao tác" else "Cần bật để điều khiển các ứng dụng khác"
        permissionText.setTextColor(if (enabled) Color.rgb(36, 137, 93) else Color.rgb(101, 108, 126))
    }

    private fun isAccessibilityEnabled(): Boolean {
        val component = ComponentName(this, PhoneAutomationService::class.java)
        val expected = setOf(component.flattenToString(), component.flattenToShortString())
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
        return enabled.split(':').any { service -> expected.any { it.equals(service, ignoreCase = true) } }
    }

    private fun openAccessibilitySettings() {
        try {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        } catch (_: Exception) {
            Toast.makeText(this, "Không mở được phần cài đặt Trợ năng.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showStatus(message: String) {
        if (::statusText.isInitialized) statusText.text = message
    }

    private fun label(text: String) = TextView(this).apply {
        this.text = text
        textSize = 11f
        letterSpacing = 0.09f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.rgb(121, 128, 146))
    }

    private fun card() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(15), dp(14), dp(15), dp(14))
        background = rounded(Color.WHITE, dp(17), Color.rgb(232, 234, 241), dp(1))
    }

    private fun row() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }

    private fun primaryButton(text: String) = Button(this).apply {
        this.text = text
        isAllCaps = false
        textSize = 15f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.WHITE)
        background = rounded(Color.rgb(99, 91, 255), dp(13), null, 0)
        minHeight = dp(50)
        stateListAnimator = null
    }

    private fun secondaryButton(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        isAllCaps = false
        textSize = 13f
        setTextColor(Color.rgb(73, 65, 215))
        background = rounded(Color.WHITE, dp(12), Color.rgb(225, 228, 237), dp(1))
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
}
