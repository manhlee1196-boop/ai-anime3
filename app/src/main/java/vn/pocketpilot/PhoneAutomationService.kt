package vn.pocketpilot

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/** All actions are started only after the user previews and taps Run in the app. */
class PhoneAutomationService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private var activeSteps: List<TaskStep> = emptyList()
    private var nextStep = 0

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        notifyStatus("Đã kết nối quyền trợ năng. Sẵn sàng thực hiện tác vụ.")
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val pending = prefs.getString(PENDING_COMMAND, null)
        if (!pending.isNullOrBlank()) {
            prefs.edit().remove(PENDING_COMMAND).apply()
            runCommand(pending)
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() { notifyStatus("Tác vụ đã bị gián đoạn.") }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (instance === this) instance = null
        super.onDestroy()
    }

    fun stopTask() {
        handler.removeCallbacksAndMessages(null)
        activeSteps = emptyList()
        nextStep = 0
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(PENDING_COMMAND).apply()
        notifyStatus("Đã dừng tác vụ theo yêu cầu.")
    }

    fun runCommand(command: String) {
        handler.removeCallbacksAndMessages(null)
        val plan = TaskPlanner.plan(this, command)
        if (plan.error != null) {
            notifyStatus(plan.error)
            return
        }
        if (plan.steps.isEmpty()) {
            notifyStatus("Không có thao tác để thực hiện.")
            return
        }
        activeSteps = plan.steps
        nextStep = 0
        notifyStatus("Đang thực hiện: ${plan.steps.first().description}")
        executeNext()
    }

    private fun executeNext() {
        if (nextStep >= activeSteps.size) {
            notifyStatus("Hoàn tất tác vụ. Hãy kiểm tra kết quả trên màn hình.")
            return
        }
        val step = activeSteps[nextStep++]
        val pauseAfter = when (step.kind) {
            StepKind.OPEN_APP -> 2200L
            StepKind.TAP_TEXT, StepKind.PRESS_ENTER -> 900L
            else -> 500L
        }
        val result = try {
            when (step.kind) {
                StepKind.OPEN_APP -> openApp(step.argument)
                StepKind.TAP_TEXT -> tapText(step.argument)
                StepKind.TYPE_TEXT -> typeText(step.argument)
                StepKind.PRESS_ENTER -> pressEnter()
                StepKind.SCROLL_DOWN -> scroll(down = true)
                StepKind.SCROLL_UP -> scroll(down = false)
                StepKind.BACK -> performGlobalAction(GLOBAL_ACTION_BACK)
                StepKind.HOME -> performGlobalAction(GLOBAL_ACTION_HOME)
            }
        } catch (_: Exception) { false }
        if (!result) {
            activeSteps = emptyList()
            nextStep = 0
            notifyStatus("Chưa thực hiện được: ${step.description}. Chuỗi đã dừng để tránh thao tác nhầm.")
            return
        }
        notifyStatus("Đã thực hiện: ${step.description}")
        handler.postDelayed({ executeNext() }, pauseAfter)
    }

    private fun openApp(packageName: String): Boolean {
        val intent = packageManager.getLaunchIntentForPackage(packageName) ?: return false
        intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
        return true
    }

    private fun tapText(target: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val search = target == TaskPlanner.SEARCH_MARKER
        val wanted = TaskPlanner.normalized(target)
        val searchWords = listOf("search", "tìm kiếm", "tim kiem", "tìm", "tim", "search here", "tra cứu", "tra cuu")
            .map(TaskPlanner::normalized)
        val candidate = findNode(root) { node ->
            val label = TaskPlanner.normalized(listOfNotNull(node.text?.toString(), node.contentDescription?.toString()).joinToString(" "))
            if (search) searchWords.any(label::contains) else label == wanted || label.contains(wanted)
        } ?: return false
        return clickNode(candidate)
    }

    private fun clickNode(candidate: AccessibilityNodeInfo): Boolean {
        var clickable: AccessibilityNodeInfo? = candidate
        repeat(5) {
            if (clickable?.isClickable == true) return clickable?.performAction(AccessibilityNodeInfo.ACTION_CLICK) ?: false
            clickable = clickable?.parent
        }
        return candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    private fun typeText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        val field = if (focused?.isEditable == true) focused else findNode(root) { it.isEditable }
        if (field == null) return false
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) }
        field.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        return field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    private fun pressEnter(): Boolean {
        val root = rootInActiveWindow ?: return false
        val field = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: findNode(root) { it.isEditable }
        if (field != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R &&
            field.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)) return true

        // On older Android versions, activate a clearly labelled submit key if the keyboard exposes one.
        val submitLabels = setOf("search", "go", "tìm", "tìm kiếm", "đi", "enter", "done")
            .map(TaskPlanner::normalized)
        val button = findNode(root) { node ->
            val label = TaskPlanner.normalized(listOfNotNull(node.text?.toString(), node.contentDescription?.toString()).joinToString(" "))
            submitLabels.any { label == it }
        } ?: return false
        return clickNode(button)
    }

    private fun scroll(down: Boolean): Boolean {
        val root = rootInActiveWindow ?: return false
        val scrollable = findNode(root) { it.isScrollable }
        val action = if (down) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        if (scrollable?.performAction(action) == true) return true

        val bounds = android.graphics.Rect()
        root.getBoundsInScreen(bounds)
        if (bounds.width() < 40 || bounds.height() < 100) return false
        val x = bounds.centerX().toFloat()
        val fromY = if (down) bounds.bottom - bounds.height() * 0.25f else bounds.top + bounds.height() * 0.25f
        val toY = if (down) bounds.top + bounds.height() * 0.25f else bounds.bottom - bounds.height() * 0.25f
        val path = Path().apply { moveTo(x, fromY); lineTo(x, toY) }
        return dispatchGesture(GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(path, 0, 400)).build(), null, null)
    }

    private fun findNode(root: AccessibilityNodeInfo, predicate: (AccessibilityNodeInfo) -> Boolean): AccessibilityNodeInfo? {
        if (predicate(root)) return root
        for (index in 0 until root.childCount) {
            val child = root.getChild(index) ?: continue
            val found = findNode(child, predicate)
            if (found != null) return found
        }
        return null
    }

    private fun notifyStatus(message: String) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(LAST_STATUS, message).apply()
        statusListener?.invoke(message)
    }

    companion object {
        const val PREFS = "pocketpilot"
        const val PENDING_COMMAND = "pending_command"
        const val LAST_STATUS = "last_status"
        @Volatile var instance: PhoneAutomationService? = null
        @Volatile var statusListener: ((String) -> Unit)? = null
    }
}
