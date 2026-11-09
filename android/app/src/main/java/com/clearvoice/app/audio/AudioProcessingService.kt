package com.clearvoice.app.audio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlin.math.ln
import kotlin.math.sqrt

/**
 * Foreground service that captures the microphone with AudioRecord, runs the
 * shared native engine (RNNoise via JNI), and optionally monitors the result
 * through AudioTrack (OFF by default — use headphones to avoid feedback).
 *
 * Honest limits: a normal app cannot replace the system microphone for other
 * apps. This service provides cleaned audio for in-app monitoring/recording;
 * system-wide routing would require system privileges.
 */
class AudioProcessingService : Service() {

    data class Stats(
        val running: Boolean = false,
        val engineName: String = "",
        val inRate: Int = 0,
        val framesProcessed: Long = 0,
        val inLevelDb: Float = -120f,
        val outLevelDb: Float = -120f,
        val vad: Float = -1f,
        val inOverflow: Long = 0,
        val outUnderflow: Long = 0,
        val cpuPercent: Float = 0f,
        val fallbackActive: Boolean = false,
        val fallbackSupported: Boolean = false,
        val error: String? = null,
        val micName: String = "",
    )

    private val statsFlow = MutableStateFlow(Stats())
    val stats: StateFlow<Stats> = statsFlow

    private val audioManager: AudioManager
        get() = getSystemService(AUDIO_SERVICE) as AudioManager

    private var captureThread: Thread? = null
    @Volatile private var stopRequested = false
    private var engine: ClearVoiceEngine? = null
    private var fallback: NoiseSuppressorFallback? = null
    private var audioRecord: AudioRecord? = null
    private var monitorTrack: AudioTrack? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        AudioProcessingServiceHolder.register(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (statsFlow.value.running) return START_STICKY
        val engineType = intent?.getIntExtra(EXTRA_ENGINE, ClearVoiceEngine.ENGINE_RNNOISE) ?: ClearVoiceEngine.ENGINE_RNNOISE
        val monitor = intent?.getBooleanExtra(EXTRA_MONITOR, false) ?: false
        val micDeviceId = intent?.getIntExtra(EXTRA_MIC_DEVICE_ID, 0) ?: 0

        startForegroundCompat()

        stopRequested = false
        captureThread = Thread({ runLoop(engineType, monitor, micDeviceId) }, "clearvoice-capture")
        captureThread?.start()
        return START_STICKY
    }

    override fun onDestroy() {
        stopRequested = true
        try {
            captureThread?.join(3000)
        } catch (_: InterruptedException) {
        }
        cleanup()
        AudioProcessingServiceHolder.unregister(this)
        super.onDestroy()
    }

    fun stopProcessing() {
        stopRequested = true
        try {
            captureThread?.join(3000)
        } catch (_: InterruptedException) {
        }
        cleanup()
        statsFlow.value = statsFlow.value.copy(running = false)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun cleanup() {
        try {
            audioRecord?.stop()
        } catch (_: Exception) {
        }
        try {
            audioRecord?.release()
        } catch (_: Exception) {
        }
        audioRecord = null
        if (Build.VERSION.SDK_INT >= 31) {
            try { audioManager.clearCommunicationDevice() } catch (_: Exception) { }
        }
        try {
            monitorTrack?.stop()
        } catch (_: Exception) {
        }
        try {
            monitorTrack?.release()
        } catch (_: Exception) {
        }
        monitorTrack = null
        engine?.close()
        engine = null
        fallback?.close()
        fallback = null
    }

    private fun runLoop(engineType: Int, monitor: Boolean, micDeviceId: Int) {
        try {
            // --- pick a sample rate: prefer 48 kHz, fall back to 44.1 kHz ---
            val sampleRate = if (AudioRecord.getMinBufferSize(48000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT) > 0) 48000 else 44100
            val channels = AudioFormat.CHANNEL_IN_MONO
            val minBuf = AudioRecord.getMinBufferSize(sampleRate, channels, AudioFormat.ENCODING_PCM_16BIT)
            if (minBuf <= 0) throw RuntimeException("no supported audio config (minBuf=$minBuf)")
            val bufSize = maxOf(minBuf, 4096)

            val builder = AudioRecord.Builder()
                .setAudioSource(MediaRecorder.AudioSource.VOICE_COMMUNICATION)
                .setAudioFormat(AudioFormat.Builder().setSampleRate(sampleRate).setChannelMask(channels).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setBufferSizeInBytes(bufSize)
            if (micDeviceId != 0) {
                // Route the communication (mic) device. AudioRecord.Builder has no
                // setPreferredDevice in this SDK stub; use AudioManager (API 31+).
                val dev = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS).firstOrNull { it.id == micDeviceId }
                if (dev != null && Build.VERSION.SDK_INT >= 31) {
                    try { audioManager.setCommunicationDevice(dev) } catch (_: Exception) { }
                }
            }
            val record = builder.build()
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                record.release()
                throw RuntimeException("AudioRecord failed to initialize")
            }
            audioRecord = record

            // --- native engine (or fallback) ---
            val eng = ClearVoiceEngine.create(engineType, sampleRate, 1)
            if (eng != null) {
                engine = eng
                statsFlow.value = statsFlow.value.copy(running = true, engineName = eng.engineName, inRate = sampleRate, micName = "")
            } else {
                // native engine unavailable -> hardware NoiseSuppressor fallback (may itself be unavailable)
                val fb = NoiseSuppressorFallback(record.audioSessionId)
                fallback = fb
                statsFlow.value = statsFlow.value.copy(running = true, engineName = "NoiseSuppressor(fallback)", inRate = sampleRate, fallbackActive = true, fallbackSupported = fb.supported)
            }

            // --- optional monitoring (default OFF; headset recommended) ---
            if (monitor) {
                val track = AudioTrack.Builder()
                    .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                    .setAudioFormat(AudioFormat.Builder().setSampleRate(48000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).setEncoding(AudioFormat.ENCODING_PCM_FLOAT).build())
                    .setBufferSizeInBytes(4096)
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .build()
                if (track.state == AudioTrack.STATE_INITIALIZED) {
                    track.play()
                    monitorTrack = track
                }
            }

            record.startRecording()
            if (record.recordingState != AudioRecord.RECORDSTATE_RECORDING) throw RuntimeException("AudioRecord failed to start recording")

            val blockFrames = bufSize / 2 // int16 mono
            val shortBuf = ShortArray(blockFrames)
            val floatOut = FloatArray(blockFrames * 2)
            var lastCpuT = System.nanoTime()
            var lastCpuC = android.os.Process.getElapsedCpuTime() / 1000 // ms, process-wide approx

            while (!stopRequested) {
                val n = record.read(shortBuf, 0, blockFrames)
                if (n <= 0) continue
                val inDb = rmsDb(shortBuf, n)
                val eng2 = engine
                if (eng2 != null && !eng2.isClosed) {
                    val rc = eng2.pushI16(shortBuf, n)
                    if (rc != 0) throw RuntimeException("nativePush error $rc")
                    val got = eng2.readOut(floatOut, floatOut.size)
                    if (got > 0 && monitorTrack != null) {
                        monitorTrack?.write(floatOut, 0, got, AudioTrack.WRITE_BLOCKING)
                    }
                    val glitches = eng2.glitchCounts()
                    val now = System.nanoTime()
                    val cpu: Float = if (now - lastCpuT > 500_000_000L) {
                        val c: Long = android.os.Process.getElapsedCpuTime() / 1000L
                        val wallSec: Double = (now - lastCpuT) / 1_000_000_000.0
                        val pct: Float = (100.0 * (c - lastCpuC) / (wallSec * 1000.0)).toFloat()
                        lastCpuT = now
                        lastCpuC = c
                        pct
                    } else statsFlow.value.cpuPercent
                    statsFlow.value = statsFlow.value.copy(
                        inLevelDb = inDb,
                        outLevelDb = rmsDbF(floatOut, got),
                        vad = eng2.lastVad,
                        framesProcessed = eng2.framesProcessed,
                        inOverflow = glitches[0],
                        outUnderflow = glitches[1],
                        cpuPercent = cpu,
                        error = null,
                    )
                } else {
                    // fallback path: NoiseSuppressor is attached to the session; audio passes through
                    val fb = fallback
                    if (fb != null && fb.supported && monitorTrack != null) {
                        val fbuf = FloatArray(n)
                        for (i in 0 until n) fbuf[i] = shortBuf[i] / 32768f
                        monitorTrack?.write(fbuf, 0, n, AudioTrack.WRITE_BLOCKING)
                    }
                    statsFlow.value = statsFlow.value.copy(inLevelDb = inDb, error = null)
                }
            }
        } catch (e: Exception) {
            statsFlow.value = statsFlow.value.copy(running = false, error = e.message ?: e.toString())
        } finally {
            cleanup()
            statsFlow.value = statsFlow.value.copy(running = false)
        }
    }

    private fun rmsDb(a: ShortArray, n: Int): Float {
        if (n <= 0) return -120f
        var p = 0.0
        for (i in 0 until n) p += (a[i].toDouble() / 32768.0) * (a[i].toDouble() / 32768.0)
        return (10.0 * ln(sqrt(p / n) + 1e-9) / ln(10.0)).toFloat()
    }

    private fun rmsDbF(a: FloatArray, n: Int): Float {
        if (n <= 0) return -120f
        var p = 0.0
        for (i in 0 until n) p += a[i].toDouble() * a[i]
        return (10.0 * ln(sqrt(p / n) + 1e-9) / ln(10.0)).toFloat()
    }

    private fun createNotificationChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        val ch = NotificationChannel(CHANNEL_ID, "ClearVoice processing", NotificationManager.IMPORTANCE_LOW)
        nm.createNotificationChannel(ch)
    }

    private fun startForegroundCompat() {
        val notif: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("ClearVoice")
            .setContentText("Noise suppression active — your microphone is being processed locally")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    companion object {
        const val CHANNEL_ID = "clearvoice_processing"
        const val NOTIF_ID = 1001
        const val EXTRA_ENGINE = "engine"
        const val EXTRA_MONITOR = "monitor"
        const val EXTRA_MIC_DEVICE_ID = "mic_device_id"
    }
}
