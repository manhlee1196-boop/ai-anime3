package vn.localpilot.app

import java.util.concurrent.TimeUnit
import kotlin.system.exitProcess

/** Runs as Shizuku's user-service identity only for a fixed, read-only diagnostic. */
class ShizukuDiagnosticService : IShizukuDiagnostic.Stub() {
    override fun countUserApps(): Int {
        val process = ProcessBuilder("sh", "-c", "cmd package list packages -3 | wc -l")
            .redirectErrorStream(true)
            .start()
        if (!process.waitFor(5, TimeUnit.SECONDS)) {
            process.destroyForcibly()
            return -1
        }
        return process.inputStream.bufferedReader().use { it.readText().trim().toIntOrNull() ?: -1 }
    }

    override fun destroy() {
        exitProcess(0)
    }
}
