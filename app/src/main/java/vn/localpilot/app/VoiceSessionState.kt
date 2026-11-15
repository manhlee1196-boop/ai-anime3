package vn.localpilot.app

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/** In-memory bridge only: voice commands are never written to disk. */
object VoiceSessionState {
    private val _active = MutableStateFlow(false)
    private val _status = MutableStateFlow("Phiên giọng nói chưa bật.")
    private val _pendingCommand = MutableStateFlow<String?>(null)

    val active = _active.asStateFlow()
    val status = _status.asStateFlow()
    val pendingCommand = _pendingCommand.asStateFlow()

    internal fun setActive(value: Boolean) { _active.value = value }
    internal fun setStatus(value: String) { _status.value = value }
    internal fun postCommand(value: String) { _pendingCommand.value = value }
    fun consumeCommand() { _pendingCommand.value = null }
}
