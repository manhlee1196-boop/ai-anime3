package vn.pocketcanvas

import android.content.Context
import android.util.Base64
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.Locale
import kotlin.random.Random

/** OpenAI-compatible image endpoint, bound only to loopback for LocalMind on this phone. */
internal class LocalImageApiServer(
    private val context: Context,
    private val modelDirectory: java.io.File,
    private val bearerToken: String,
    private val onStatus: (String) -> Unit
) {
    @Volatile private var running = false
    private var serverSocket: ServerSocket? = null
    private var acceptThread: Thread? = null

    @Synchronized
    fun start() {
        if (running) return
        val socket = ServerSocket()
        socket.reuseAddress = true
        socket.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), PORT), 2)
        serverSocket = socket
        running = true
        acceptThread = Thread({ acceptLoop(socket) }, "pocketcanvas-local-api").apply {
            isDaemon = true
            start()
        }
        onStatus("API sẵn sàng tại http://127.0.0.1:$PORT/v1 — chỉ nhận kết nối từ chính điện thoại.")
    }

    @Synchronized
    fun stop() {
        running = false
        try { serverSocket?.close() } catch (_: Exception) { }
        serverSocket = null
        acceptThread?.interrupt()
        acceptThread = null
    }

    private fun acceptLoop(listener: ServerSocket) {
        while (running) {
            try {
                listener.accept().use { socket ->
                    socket.soTimeout = CLIENT_TIMEOUT_MS
                    handle(socket)
                }
            } catch (_: Exception) {
                if (running) onStatus("Local API gặp lỗi kết nối; thử tắt rồi bật lại.")
            }
        }
    }

    private fun handle(socket: Socket) {
        val input = BufferedInputStream(socket.getInputStream())
        val requestLine = readLine(input) ?: return
        val requestParts = requestLine.split(' ', limit = 3)
        if (requestParts.size < 2) {
            sendError(socket.getOutputStream(), 400, "Yêu cầu HTTP không hợp lệ.")
            return
        }
        val method = requestParts[0].uppercase(Locale.ROOT)
        val path = requestParts[1].substringBefore('?')
        val headers = mutableMapOf<String, String>()
        while (true) {
            val line = readLine(input) ?: break
            if (line.isEmpty()) break
            val colon = line.indexOf(':')
            if (colon > 0) headers[line.substring(0, colon).trim().lowercase(Locale.ROOT)] = line.substring(colon + 1).trim()
        }
        if (!authorized(headers["authorization"])) {
            sendError(socket.getOutputStream(), 401, "Thiếu hoặc sai local API key.", "authentication_error")
            return
        }

        when {
            method == "GET" && (path == "/v1/models" || path == "/v1/models/") -> sendJson(socket.getOutputStream(), 200, modelList())
            method == "GET" && path == "/v1/models/$MODEL_ID" -> sendJson(socket.getOutputStream(), 200, modelInfo())
            method == "POST" && path == "/v1/images/generations" -> handleGeneration(socket, input, headers)
            else -> sendError(socket.getOutputStream(), 404, "Không hỗ trợ endpoint này.", "not_found")
        }
    }

    private fun handleGeneration(socket: Socket, input: BufferedInputStream, headers: Map<String, String>) {
        val length = headers["content-length"]?.toLongOrNull()
        if (length == null || length < 1 || length > MAX_REQUEST_BYTES) {
            sendError(socket.getOutputStream(), 413, "Content-Length thiếu hoặc prompt vượt giới hạn.")
            return
        }
        val body = ByteArray(length.toInt())
        var offset = 0
        while (offset < body.size) {
            val count = input.read(body, offset, body.size - offset)
            if (count < 0) {
                sendError(socket.getOutputStream(), 400, "Request body chưa đầy đủ.")
                return
            }
            offset += count
        }
        try {
            val request = JSONObject(String(body, StandardCharsets.UTF_8))
            val requestedModel = request.optString("model", MODEL_ID)
            if (requestedModel != MODEL_ID) {
                sendError(socket.getOutputStream(), 400, "Model không tồn tại: $requestedModel")
                return
            }
            if (request.optInt("n", 1) != 1) {
                sendError(socket.getOutputStream(), 400, "PocketCanvas hỗ trợ một ảnh cho mỗi request.")
                return
            }
            val prompt = request.optString("prompt", "").trim()
            if (prompt.isEmpty() || prompt.length > 4000) {
                sendError(socket.getOutputStream(), 400, "Prompt phải có từ 1 đến 4000 ký tự.")
                return
            }
            val steps = request.optInt("steps", DEFAULT_STEPS).coerceIn(5, 20)
            val seed = request.optInt("seed", Random.nextInt(0, Int.MAX_VALUE))
            onStatus("LocalMind đang tạo ảnh trên điện thoại…")
            val png = DiffusionRuntime.generatePng(context, modelDirectory, prompt, steps, seed)
            val item = JSONObject().put("b64_json", Base64.encodeToString(png, Base64.NO_WRAP))
            val response = JSONObject()
                .put("created", System.currentTimeMillis() / 1000L)
                .put("data", JSONArray().put(item))
            sendJson(socket.getOutputStream(), 200, response)
            onStatus("LocalMind đã nhận ảnh tạo xong. Seed: $seed")
        } catch (error: Exception) {
            Log.e("PocketCanvas", "LocalMind image request failed", error)
            val message = ImageGenErrorMessages.explain(error)
            sendError(socket.getOutputStream(), 500, message, "server_error")
            onStatus(message)
        }
    }

    private fun modelList(): JSONObject = JSONObject()
        .put("object", "list")
        .put("data", JSONArray().put(modelInfo()))

    private fun modelInfo(): JSONObject = JSONObject()
        .put("id", MODEL_ID)
        .put("object", "model")
        .put("created", 0)
        .put("owned_by", "pocketcanvas-local")

    private fun authorized(header: String?): Boolean {
        val presented = header?.takeIf { it.startsWith("Bearer ", ignoreCase = true) }?.substringAfter(' ')
            ?: return false
        return MessageDigest.isEqual(
            presented.toByteArray(StandardCharsets.UTF_8),
            bearerToken.toByteArray(StandardCharsets.UTF_8)
        )
    }

    private fun sendError(output: OutputStream, code: Int, message: String, type: String = "invalid_request_error") {
        val payload = JSONObject().put("error", JSONObject().put("message", message).put("type", type))
        sendJson(output, code, payload)
    }

    private fun sendJson(output: OutputStream, code: Int, body: JSONObject) {
        val bytes = body.toString().toByteArray(StandardCharsets.UTF_8)
        val reason = when (code) {
            200 -> "OK"
            400 -> "Bad Request"
            401 -> "Unauthorized"
            404 -> "Not Found"
            413 -> "Payload Too Large"
            else -> "Internal Server Error"
        }
        val header = "HTTP/1.1 $code $reason\r\n" +
            "Content-Type: application/json; charset=utf-8\r\n" +
            "Content-Length: ${bytes.size}\r\n" +
            "Cache-Control: no-store\r\n" +
            "Connection: close\r\n\r\n"
        output.write(header.toByteArray(StandardCharsets.US_ASCII))
        output.write(bytes)
        output.flush()
    }

    private fun readLine(input: BufferedInputStream): String? {
        val bytes = ByteArrayOutputStream()
        while (bytes.size() <= MAX_HEADER_LINE) {
            val next = input.read()
            if (next < 0) return if (bytes.size() == 0) null else String(bytes.toByteArray(), StandardCharsets.US_ASCII)
            if (next == '\n'.code) return String(bytes.toByteArray(), StandardCharsets.US_ASCII).trimEnd('\r')
            bytes.write(next)
        }
        throw IllegalArgumentException("HTTP header line quá dài.")
    }

    companion object {
        const val PORT = 8765
        const val MODEL_ID = "pocketcanvas-sd15"
        private const val DEFAULT_STEPS = 10
        private const val MAX_REQUEST_BYTES = 1024L * 1024L
        private const val MAX_HEADER_LINE = 16 * 1024
        private const val CLIENT_TIMEOUT_MS = 180_000
    }
}
