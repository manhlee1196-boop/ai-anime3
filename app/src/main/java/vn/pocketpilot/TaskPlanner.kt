package vn.pocketpilot

import android.content.Context
import android.content.pm.PackageManager
import java.text.Normalizer
import java.util.Locale

internal enum class StepKind { OPEN_APP, TAP_TEXT, TYPE_TEXT, PRESS_ENTER, SCROLL_DOWN, SCROLL_UP, BACK, HOME }
internal data class TaskStep(val kind: StepKind, val argument: String = "", val description: String)
internal data class TaskPlan(val steps: List<TaskStep>, val error: String? = null)

/** A small, fully on-device intent interpreter. It never sends a task to a server. */
internal object TaskPlanner {
    fun normalized(value: String): String = Normalizer.normalize(value.lowercase(Locale.ROOT), Normalizer.Form.NFD)
        .replace("\\p{Mn}+".toRegex(), "")
        .replace('đ', 'd')
        .trim()

    fun plan(context: Context, raw: String): TaskPlan {
        val command = raw.trim()
        if (command.isBlank()) return TaskPlan(emptyList(), "Hãy nhập một yêu cầu trước.")
        val n = normalized(command)

        // High-impact operations are intentionally not automated in this first version.
        val blocked = listOf("chuyen tien", "thanh toan", "mua hang", "xoa tai khoan", "gui tin nhan", "gui email", "dang bai")
        if (blocked.any(n::contains)) {
            return TaskPlan(emptyList(), "PocketPilot hiện không tự gửi tin, đăng bài, mua hàng, thanh toán hoặc xóa dữ liệu. Bạn có thể tự hoàn tất bước cuối trong ứng dụng.")
        }

        when {
            listOf("ve man hinh chinh", "tro ve man hinh chinh", "home").any(n::contains) ->
                return TaskPlan(listOf(TaskStep(StepKind.HOME, description = "Về màn hình chính")))
            listOf("quay lai", "tro lai", "back").any(n::contains) ->
                return TaskPlan(listOf(TaskStep(StepKind.BACK, description = "Quay lại")))
            listOf("cuon xuong", "keo xuong", "scroll down").any(n::contains) ->
                return TaskPlan(listOf(TaskStep(StepKind.SCROLL_DOWN, description = "Cuộn xuống")))
            listOf("cuon len", "keo len", "scroll up").any(n::contains) ->
                return TaskPlan(listOf(TaskStep(StepKind.SCROLL_UP, description = "Cuộn lên")))
        }

        val openMatch = Regex("(?i)^(?:mở|mo|open)\\s+(.+?)(?:\\s+(?:và\\s+)?(?:tìm|tim|search)\\s+(.+))?$").matchEntire(command)
        if (openMatch != null) {
            val appName = openMatch.groupValues[1].trim().trimEnd('.', '!')
            val app = findApp(context, appName)
                ?: return TaskPlan(emptyList(), "Không tìm thấy ứng dụng “$appName” đã cài. Hãy thử ghi đúng tên hiển thị của ứng dụng.")
            val steps = mutableListOf(TaskStep(StepKind.OPEN_APP, app.packageName, "Mở ${app.label}"))
            val query = openMatch.groupValues.getOrNull(2)?.trim()?.trimEnd('.', '!').orEmpty()
            if (query.isNotBlank()) {
                steps += TaskStep(StepKind.TAP_TEXT, SEARCH_MARKER, "Tìm ô tìm kiếm")
                steps += TaskStep(StepKind.TYPE_TEXT, query, "Nhập “$query”")
                steps += TaskStep(StepKind.PRESS_ENTER, description = "Thực hiện tìm kiếm")
            }
            return TaskPlan(steps)
        }

        val searchMatch = Regex("(?i)^(?:tìm|tim|search)\\s+(.+)$").matchEntire(command)
        if (searchMatch != null) {
            val query = searchMatch.groupValues[1].trim().trimEnd('.', '!')
            return TaskPlan(listOf(
                TaskStep(StepKind.TAP_TEXT, SEARCH_MARKER, "Tìm ô tìm kiếm"),
                TaskStep(StepKind.TYPE_TEXT, query, "Nhập “$query”"),
                TaskStep(StepKind.PRESS_ENTER, description = "Thực hiện tìm kiếm")
            ))
        }

        val tapMatch = Regex("(?i)^(?:nhấn|bấm|chạm|tap)\\s+(.+)$").matchEntire(command)
        if (tapMatch != null) {
            val target = tapMatch.groupValues[1].trim().trimEnd('.', '!')
            return TaskPlan(listOf(TaskStep(StepKind.TAP_TEXT, target, "Nhấn “$target”")))
        }
        val typeMatch = Regex("(?i)^(?:nhập|gõ|type)\\s+(.+)$").matchEntire(command)
        if (typeMatch != null) {
            val text = typeMatch.groupValues[1].trim().trimEnd('.', '!')
            return TaskPlan(listOf(TaskStep(StepKind.TYPE_TEXT, text, "Nhập “$text” vào ô đang chọn")))
        }
        return TaskPlan(emptyList(), "Mình chưa hiểu yêu cầu. Thử: “Mở YouTube”, “Mở Chrome và tìm công thức phở”, “Nhấn Cài đặt”, “Cuộn xuống” hoặc “Quay lại”.")
    }

    private data class AppMatch(val packageName: String, val label: String)

    private fun findApp(context: Context, requested: String): AppMatch? {
        val pm = context.packageManager
        val wanted = normalized(requested).removeSuffix(" app").trim()
        val aliases = listOf(
            listOf("youtube", "com.google.android.youtube"),
            listOf("chrome", "com.android.chrome"),
            listOf("zalo", "com.zing.zalo"),
            listOf("facebook", "com.facebook.katana"),
            listOf("messenger", "com.facebook.orca"),
            listOf("gmail", "com.google.android.gm"),
            listOf("google maps", "com.google.android.apps.maps"),
            listOf("maps", "com.google.android.apps.maps"),
            listOf("tiktok", "com.zhiliaoapp.musically"),
            listOf("settings", "com.android.settings"),
            listOf("cài đặt", "com.android.settings"),
            listOf("camera", "com.android.camera2"),
            listOf("máy ảnh", "com.android.camera2")
        )
        aliases.firstOrNull { normalized(it[0]) == wanted }?.let { pair ->
            val intent = pm.getLaunchIntentForPackage(pair[1])
            if (intent != null) {
                val label = try { pm.getApplicationLabel(pm.getApplicationInfo(pair[1], 0)).toString() } catch (_: Exception) { requested }
                return AppMatch(pair[1], label)
            }
        }
        return try {
            @Suppress("DEPRECATION")
            pm.getInstalledApplications(PackageManager.GET_META_DATA)
                .asSequence()
                .mapNotNull { info ->
                    val launch = pm.getLaunchIntentForPackage(info.packageName) ?: return@mapNotNull null
                    val label = pm.getApplicationLabel(info).toString()
                    val labelN = normalized(label)
                    val score = when {
                        wanted == labelN -> 0
                        labelN.startsWith(wanted) -> 1
                        wanted.startsWith(labelN) && labelN.length > 2 -> 2
                        else -> return@mapNotNull null
                    }
                    Triple(score, info.packageName, label)
                }
                .sortedBy { it.first }
                .firstOrNull()
                ?.let { AppMatch(it.second, it.third) }
        } catch (_: Exception) { null }
    }

    const val SEARCH_MARKER = "__pocketpilot_search__"
}
