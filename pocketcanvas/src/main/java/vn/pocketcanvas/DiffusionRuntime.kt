package vn.pocketcanvas

import android.content.Context
import android.graphics.Bitmap
import com.google.mediapipe.framework.image.BitmapExtractor
import com.google.mediapipe.tasks.vision.imagegenerator.ImageGenerator
import com.google.mediapipe.tasks.vision.imagegenerator.ImageGenerator.ImageGeneratorOptions
import java.io.ByteArrayOutputStream
import java.io.File

/** One serialized model instance shared by the app UI and the loopback API. */
internal object DiffusionRuntime {
    private var generator: ImageGenerator? = null
    private var loadedPath: String? = null

    @Synchronized
    fun generateBitmap(context: Context, modelDirectory: File, prompt: String, steps: Int, seed: Int): Bitmap {
        require(steps in 1..30) { "Số bước không hợp lệ." }
        require(prompt.isNotBlank() && prompt.length <= 4000) { "Prompt trống hoặc quá dài." }
        val path = modelDirectory.canonicalPath
        if (generator == null || loadedPath != path) {
            generator?.close()
            val options = ImageGeneratorOptions.builder()
                .setImageGeneratorModelDirectory(path)
                .build()
            generator = ImageGenerator.createFromOptions(context.applicationContext, options)
            loadedPath = path
        }
        val result = generator!!.generate(prompt, steps, seed)
        val generated = result?.generatedImage() ?: error("Model không trả ảnh kết quả.")
        return BitmapExtractor.extract(generated)
    }

    @Synchronized
    fun generatePng(context: Context, modelDirectory: File, prompt: String, steps: Int, seed: Int): ByteArray {
        val bitmap = generateBitmap(context, modelDirectory, prompt, steps, seed)
        return try {
            ByteArrayOutputStream().use { output ->
                check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) { "Không mã hóa được ảnh PNG." }
                output.toByteArray()
            }
        } finally {
            bitmap.recycle()
        }
    }

    @Synchronized
    fun close() {
        try { generator?.close() } finally {
            generator = null
            loadedPath = null
        }
    }
}
