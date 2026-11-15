package vn.pocketcanvas

import android.os.Build
import java.util.Locale

internal object ImageGenErrorMessages {
    fun explain(error: Throwable): String {
        val causes = generateSequence(error) { it.cause }.take(8).toList()
        val details = causes.joinToString(" ") { it.message.orEmpty() }.lowercase(Locale.ROOT)
        val isGraphFailure = listOf(
            "clcreateimage",
            "invalid image size",
            "stable_diffusion_iterate_calculator",
            "calculatorgraph::run() failed"
        ).any { marker -> details.contains(marker) }
        val hasExplicitOpenClError = details.contains("clcreateimage") || details.contains("invalid image size")

        if (isGraphFailure && hasExplicitOpenClError) {
            return "Log MediaPipe có dấu hiệu lỗi GPU/OpenCL (clCreateImage / image size), nhưng chưa xác định chắc nguyên nhân. Có thể liên quan driver/giới hạn GPU, bộ nhớ khả dụng hoặc gói model; kiểm tra ZIP sd15-mediapipe đã tải đủ, đóng ứng dụng nền rồi thử lại. Máy: ${Build.MANUFACTURER} ${Build.MODEL}, Android ${Build.VERSION.RELEASE}. Chi tiết: xem Logcat với tag PocketCanvas."
        }
        if (isGraphFailure) {
            return "MediaPipe không chạy được graph tạo ảnh, nhưng lỗi này chưa đủ để kết luận nguyên nhân là OpenCL. Có thể liên quan GPU/driver, tài nguyên hoặc gói model. Kiểm tra ZIP sd15-mediapipe đã tải đủ; gửi Logcat ngay trước lỗi để chẩn đoán. Máy: ${Build.MANUFACTURER} ${Build.MODEL}, Android ${Build.VERSION.RELEASE}."
        }
        return "Không tạo được ảnh: ${error.message ?: "kiểm tra model và dung lượng bộ nhớ trống"}"
    }
}
