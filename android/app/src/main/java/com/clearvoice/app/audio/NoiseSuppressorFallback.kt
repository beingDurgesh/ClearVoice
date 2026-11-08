package com.clearvoice.app.audio

import android.media.audiofx.NoiseSuppressor

/**
 * Fallback path when the native RNNoise engine is unavailable (e.g. the .so
 * failed to load on an exotic ABI). Uses the device's hardware NoiseSuppressor
 * AudioEffect attached to the AudioRecord audio session.
 *
 * IMPORTANT: NoiseSuppressor.isAvailable() is false on many devices — the
 * official docs require checking it. When unavailable, this class is a no-op
 * (passthrough) and the UI must say so.
 */
class NoiseSuppressorFallback(audioSessionId: Int) : AutoCloseable {

    private var ns: NoiseSuppressor? = null
    val supported: Boolean

    init {
        supported = try {
            NoiseSuppressor.isAvailable().also { ok ->
                if (ok) {
                    ns = NoiseSuppressor.create(audioSessionId).apply { enabled = true }
                }
            }
        } catch (e: Exception) {
            false
        }
    }

    fun setEnabled(on: Boolean) {
        try {
            ns?.enabled = on
        } catch (_: Exception) {
        }
    }

    override fun close() {
        try {
            ns?.release()
        } catch (_: Exception) {
        }
        ns = null
    }
}
