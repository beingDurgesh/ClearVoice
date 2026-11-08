package com.clearvoice.app.audio

/**
 * Kotlin facade over the shared native core (libclearvoice_core.so).
 *
 * The native methods are static and handle-based; the .so is built from the
 * same core/ sources as the Windows DLL. If the library cannot be loaded or
 * nativeCreate fails, [available] is false and the caller should use
 * [NoiseSuppressorFallback] instead.
 */
class ClearVoiceEngine private constructor(val handle: Long) {

    val inRate: Int get() = nativeInRate(handle)
    val engineName: String get() = nativeEngineName(handle)
    val framesProcessed: Long get() = nativeFramesProcessed(handle)
    val lastVad: Float get() = nativeLastVad(handle)
    val available: Int get() = nativeRingAvailable(handle)

    /** Push interleaved int16 PCM; returns CvError (0 = OK). */
    fun pushI16(samples: ShortArray, frames: Int): Int = nativePushI16(handle, samples, frames)

    /** Push interleaved float32 PCM; returns CvError (0 = OK). */
    fun pushF32(samples: FloatArray, frames: Int): Int = nativePushF32(handle, samples, frames)

    /** Read processed 48 kHz mono float32 into dst (zero-padded); returns samples read. */
    fun readOut(dst: FloatArray, maxSamples: Int): Int = nativeReadOut(handle, dst, maxSamples)

    /** Glitch counters: [outputRingOverflow, outputRingUnderflow]. */
    fun glitchCounts(): LongArray = nativeGlitchCounts(handle) ?: longArrayOf(0, 0)

    fun close() {
        if (handle != 0L) {
            nativeDestroy(handle)
            // handle invalid after destroy; mark via reflection-free sentinel
            destroyed = true
        }
    }

    private var destroyed = false
    val isClosed: Boolean get() = destroyed

    companion object {
        const val ENGINE_PASSTHROUGH = 0
        const val ENGINE_RNNOISE = 1

        @Volatile
        var loadError: String? = null
            private set

        init {
            loadError = try {
                System.loadLibrary("clearvoice_core")
                null
            } catch (e: UnsatisfiedLinkError) {
                e.message
            } catch (e: SecurityException) {
                e.message
            }
        }

        /** True if the native library loaded successfully. */
        val nativeAvailable: Boolean get() = loadError == null

        /**
         * Create an engine. Returns null if the native lib is missing or creation fails.
         * @param engineType ENGINE_RNNOISE or ENGINE_PASSTHROUGH
         * @param inSampleRate AudioRecord sample rate (any common rate; resampled to 48 kHz internally)
         * @param inChannels AudioRecord channel count (1 or 2)
         */
        fun create(engineType: Int, inSampleRate: Int, inChannels: Int): ClearVoiceEngine? {
            if (!nativeAvailable) return null
            val h = nativeCreate(engineType, inSampleRate, inChannels, 48000 * 2)
            return if (h == 0L) null else ClearVoiceEngine(h)
        }

        @JvmStatic external fun nativeCreate(engineType: Int, inSampleRate: Int, inChannels: Int, outRingCapacity: Int): Long
        @JvmStatic external fun nativeDestroy(handle: Long)
        @JvmStatic external fun nativePushI16(handle: Long, samples: ShortArray, frames: Int): Int
        @JvmStatic external fun nativePushF32(handle: Long, samples: FloatArray, frames: Int): Int
        @JvmStatic external fun nativeReadOut(handle: Long, dst: FloatArray, maxSamples: Int): Int
        @JvmStatic external fun nativeRingAvailable(handle: Long): Int
        @JvmStatic external fun nativeLastVad(handle: Long): Float
        @JvmStatic external fun nativeFramesProcessed(handle: Long): Long
        @JvmStatic external fun nativeGlitchCounts(handle: Long): LongArray
        @JvmStatic external fun nativeEngineName(handle: Long): String
        @JvmStatic external fun nativeInRate(handle: Long): Int
    }
}
