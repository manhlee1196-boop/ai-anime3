package vn.localpilot.app

import android.accessibilityservice.AccessibilityService
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.lang.ref.WeakReference

/** Opt-in, one-shot screen reader and user-approved, allowlisted UI action runner. */
class ScreenAccessService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())

    override fun onServiceConnected() {
        active = WeakReference(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val eventPackage = event?.packageName?.toString() ?: return
        if (eventPackage == packageName || eventPackage in IGNORED_SYSTEM_PACKAGES) return
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED &&
            event.eventType != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) return

        val shouldCapture = synchronized(stateLock) { captureArmed && !captureScheduled }
        if (shouldCapture) scheduleOneShotCapture()
        maybeStartQueuedPlan(eventPackage)
    }

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        synchronized(stateLock) {
            if (active?.get() === this) active = null
            queuedPlan = null
            planRunning = false
            planCancelled = false
            planTargetPackage = null
            captureArmed = false
            captureScheduled = false
            capturedScreen = null
            actionResult = null
        }
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun scheduleOneShotCapture() {
        synchronized(stateLock) {
            if (!captureArmed || captureScheduled) return
            captureScheduled = true
        }
        handler.postDelayed({
            val root = rootInActiveWindow
            val targetPackage = root?.packageName?.toString()
            val text = if (root != null && targetPackage != null && targetPackage != packageName &&
                targetPackage !in IGNORED_SYSTEM_PACKAGES) extractText(root) else ""
            synchronized(stateLock) {
                captureScheduled = false
                if (captureArmed && text.isNotBlank() && targetPackage != null) {
                    capturedScreen = CapturedScreen(text, targetPackage)
                    captureArmed = false
                }
            }
        }, CAPTURE_DEBOUNCE_MS)
    }

    private fun maybeStartQueuedPlan(eventPackage: String) {
        val queued = synchronized(stateLock) {
            val actions = queuedPlan
            val target = planTargetPackage
            if (actions == null || planRunning || eventPackage != target) null
            else if (SystemClock.elapsedRealtime() >= planExpiresAt) {
                queuedPlan = null
                planTargetPackage = null
                planRunning = false
                actionResult = "Kế hoạch hết hạn; không có thao tác nào được chạy."
                null
            } else if (target.isNullOrBlank()) {
                queuedPlan = null
                planRunning = false
                null
            } else {
                queuedPlan = null
                planRunning = true
                actions to target!!
            }
        } ?: return

        handler.postDelayed({ runPlanStep(queued.first, 0, queued.second) }, ACTION_START_DELAY_MS)
    }

    private fun runPlanStep(actions: List<UiAction>, index: Int, targetPackage: String) {
        val cancelled = synchronized(stateLock) { planCancelled }
        if (cancelled) {
            finishPlan("Đã dừng macro theo yêu cầu.")
            return
        }
        if (SystemClock.elapsedRealtime() >= planExpiresAt) {
            finishPlan("Kế hoạch hết hạn giữa chừng; đã dừng sau $index/${actions.size} bước.")
            return
        }
        val root = rootInActiveWindow
        if (root?.packageName?.toString() != targetPackage) {
            finishPlan("Đã dừng macro vì ứng dụng đích thay đổi.")
            return
        }
        val step = actions[index]
        val success = when (step) {
            is UiAction.Tap -> clickExactLabel(step.label)
            is UiAction.Type -> typeIntoField(step.label, step.text)
        }
        if (!success) {
            finishPlan("Đã chạy $index/${actions.size} bước rồi dừng: nhãn/ô nhập không còn khớp hoặc ứng dụng từ chối thao tác.")
            return
        }
        if (index + 1 == actions.size) {
            finishPlan("Đã chạy xong ${actions.size} bước. Không tự gửi biểu mẫu hay tin nhắn.")
        } else {
            handler.postDelayed({ runPlanStep(actions, index + 1, targetPackage) }, ACTION_STEP_DELAY_MS)
        }
    }

    private fun finishPlan(message: String) {
        synchronized(stateLock) {
            planRunning = false
            planCancelled = false
            queuedPlan = null
            planTargetPackage = null
            actionResult = message
        }
    }

    private fun extractText(root: AccessibilityNodeInfo): String {
        val lines = LinkedHashSet<String>()
        collectText(root, lines, 0, intArrayOf(0))
        return lines.take(120).joinToString("\n").take(8_000)
    }

    private fun collectText(node: AccessibilityNodeInfo, out: MutableSet<String>, depth: Int, visited: IntArray) {
        if (depth > 24 || visited[0]++ > 800) return
        if (node.isVisibleToUser && !node.isPassword) {
            if (node.isEditable) {
                val hint = inputHint(node)
                // Expose the accessible hint only; never read the user's current field contents.
                if (hint.length in 2..120) out.add("INPUT: $hint")
            } else {
                val value = (node.text ?: node.contentDescription)?.toString()?.trim().orEmpty()
                if (value.length in 2..240) out.add(value)
            }
        }
        for (i in 0 until node.childCount) node.getChild(i)?.let { collectText(it, out, depth + 1, visited) }
    }

    /** Only clicks an exact, currently visible, non-editable text label. */
    fun clickExactLabel(label: String): Boolean {
        val root = rootInActiveWindow ?: return false
        return clickNode(root, label.trim(), 0, intArrayOf(0))
    }

    /** Replaces text only in a visible, non-password field with this exact accessible hint. */
    fun typeIntoField(exactHint: String, value: String): Boolean {
        if (value.length > 500) return false
        val root = rootInActiveWindow ?: return false
        return setTextNode(root, exactHint.trim(), value, 0, intArrayOf(0))
    }

    private fun clickNode(node: AccessibilityNodeInfo, label: String, depth: Int, visited: IntArray): Boolean {
        if (depth > 24 || visited[0]++ > 800) return false
        if (node.isVisibleToUser && !node.isPassword && !node.isEditable) {
            val text = (node.text ?: node.contentDescription)?.toString()?.trim()
            if (text == label) {
                var candidate: AccessibilityNodeInfo? = AccessibilityNodeInfo.obtain(node)
                repeat(6) {
                    if (candidate?.isClickable == true) return candidate?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true
                    candidate = candidate?.parent
                }
                return false
            }
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            if (clickNode(child, label, depth + 1, visited)) return true
        }
        return false
    }

    private fun setTextNode(node: AccessibilityNodeInfo, hint: String, value: String, depth: Int, visited: IntArray): Boolean {
        if (depth > 24 || visited[0]++ > 800) return false
        if (node.isVisibleToUser && node.isEditable && !node.isPassword && inputHint(node) == hint) {
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
            }
            return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            if (setTextNode(child, hint, value, depth + 1, visited)) return true
        }
        return false
    }

    private fun inputHint(node: AccessibilityNodeInfo): String =
        (node.hintText ?: node.contentDescription)?.toString()?.trim().orEmpty()

    companion object {
        private const val CAPTURE_DEBOUNCE_MS = 450L
        private const val ACTION_START_DELAY_MS = 350L
        private const val ACTION_STEP_DELAY_MS = 550L
        private val IGNORED_SYSTEM_PACKAGES = setOf(
            "com.android.systemui", "com.android.launcher3", "com.google.android.apps.nexuslauncher",
            "com.sec.android.app.launcher", "com.miui.home", "com.huawei.android.launcher",
            "com.oppo.launcher", "com.oneplus.launcher"
        )
        private val BLOCKED_LABELS = listOf(
            "pay", "purchase", "buy", "delete", "remove", "send", "post", "submit", "transfer", "confirm", "approve",
            "thanh toán", "mua", "xóa", "xoá", "gửi", "đăng", "nộp", "chuyển tiền", "xác nhận", "phê duyệt", "đồng ý"
        )
        private val stateLock = Any()

        private fun isSensitiveInputLabel(label: String): Boolean {
            val lower = label.lowercase()
            if (listOf("mật khẩu", "mã xác thực", "mã otp", "thẻ ngân hàng").any { lower.contains(it) }) return true
            val tokens = lower.split(Regex("[^\\p{L}\\p{N}]+"))
            return tokens.any { it in setOf("password", "passcode", "otp", "pin", "cvv", "verification") }
        }
        @Volatile private var active: WeakReference<ScreenAccessService>? = null
        private var captureArmed = false
        private var captureScheduled = false
        private var capturedScreen: CapturedScreen? = null
        private var queuedPlan: List<UiAction>? = null
        private var planTargetPackage: String? = null
        private var planExpiresAt: Long = 0
        private var planRunning = false
        private var planCancelled = false
        private var actionResult: String? = null

        fun instance(): ScreenAccessService? = active?.get()

        fun armNextScreenCapture(): Boolean {
            if (instance() == null) return false
            synchronized(stateLock) {
                if (captureScheduled) return false
                capturedScreen = null
                captureArmed = true
            }
            return true
        }

        fun consumeCapturedScreen(): CapturedScreen? = synchronized(stateLock) {
            capturedScreen.also { capturedScreen = null }
        }

        fun cancelScreenCapture() {
            synchronized(stateLock) {
                captureArmed = false
                captureScheduled = false
                capturedScreen = null
            }
        }

        fun queueApprovedPlan(actions: List<UiAction>, targetPackage: String?): Boolean {
            val service = instance() ?: return false
            if (targetPackage.isNullOrBlank() || actions.isEmpty() || actions.size > 5) return false
            if (actions.any { action ->
                    action.label.length !in 2..120 || when (action) {
                        is UiAction.Tap -> BLOCKED_LABELS.any { action.label.contains(it, ignoreCase = true) }
                        is UiAction.Type -> action.text.isBlank() || action.text.length > 500 || isSensitiveInputLabel(action.label)
                    }
                }) return false
            val accepted = synchronized(stateLock) {
                if (queuedPlan != null || planRunning) false
                else {
                    queuedPlan = actions.toList()
                    planTargetPackage = targetPackage
                    planExpiresAt = SystemClock.elapsedRealtime() + PLAN_TTL_MS
                    planRunning = false
                    planCancelled = false
                    actionResult = null
                    true
                }
            }
            if (!accepted) return false
            service.handler.postDelayed({
                val activePackage = service.rootInActiveWindow?.packageName?.toString()
                if (activePackage == targetPackage) service.maybeStartQueuedPlan(activePackage)
            }, ACTION_START_DELAY_MS)
            service.handler.postDelayed({
                synchronized(stateLock) {
                    if (queuedPlan != null && SystemClock.elapsedRealtime() >= planExpiresAt) {
                        queuedPlan = null
                        planTargetPackage = null
                        actionResult = "Kế hoạch hết hạn sau 30 giây; không có thao tác nào được chạy."
                    }
                }
            }, PLAN_TTL_MS)
            return true
        }

        fun cancelAutomation(): Boolean = synchronized(stateLock) {
            val hadQueuedPlan = queuedPlan != null
            val wasRunning = planRunning
            queuedPlan = null
            if (wasRunning) {
                planCancelled = true
            } else {
                planTargetPackage = null
                planCancelled = false
                if (hadQueuedPlan) actionResult = "Đã hủy kế hoạch đang chờ; không có thao tác nào được chạy."
            }
            hadQueuedPlan || wasRunning
        }

        fun consumeActionResult(): String? = synchronized(stateLock) {
            actionResult.also { actionResult = null }
        }

        private const val PLAN_TTL_MS = 30_000L
    }
}

data class CapturedScreen(val text: String, val packageName: String)
