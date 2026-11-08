package com.clearvoice.app

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.clearvoice.app.audio.AudioProcessingService
import com.clearvoice.app.audio.ClearVoiceEngine
import com.clearvoice.app.audio.DeviceMonitor

private val BG = Color(0xFF0B1220)
private val PANEL = Color(0xFF111827)
private val ACCENT = Color(0xFF22C55E)
private val WARN = Color(0xFFFBBF24)
private val ERR = Color(0xFFEF4444)

class MainActivity : ComponentActivity() {

    private lateinit var deviceMonitor: DeviceMonitor
    private var service: AudioProcessingService? = null
    private var bound = false

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            // Service is started, not bound; stats come via a static flow holder.
        }

        override fun onServiceDisconnected(name: ComponentName?) {}
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        deviceMonitor = DeviceMonitor(this)
        setContent { ClearVoiceTheme { Dashboard() }
    }

    @Composable
    private fun Dashboard() {
        var hasMicPerm by remember { mutableStateOf(hasRecordPermission()) }
        var running by remember { mutableStateOf(false) }
        var engine by remember { mutableStateOf(ClearVoiceEngine.ENGINE_RNNOISE) }
        var monitor by remember { mutableStateOf(false) }
        var mics by remember { mutableStateOf(deviceMonitor.listInputDevices()) }
        var selectedMic by remember { mutableStateOf(0) }
        var expanded by remember { mutableStateOf(false) }
        val stats by StatsHolder.flow.collectAsState()

        LaunchedEffect(Unit) {
            StatsHolder.attach(this@MainActivity)
        }

        val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            hasMicPerm = granted
        }

        Column(
            modifier = Modifier.fillMaxSize().background(BG).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("ClearVoice", style = MaterialTheme.typography.headlineLarge, color = Color.White)
            Text("Your voice. Less noise.", color = Color.Gray)

            if (!hasMicPerm) {
                Text("Microphone permission is required. Audio is processed locally and never uploaded.", color = WARN)
                Button(onClick = { permLauncher.launch(Manifest.permission.RECORD_AUDIO) }) { Text("Grant microphone permission") }
            }
            if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                OutlinedButton(onClick = { permLauncher.launch(Manifest.permission.POST_NOTIFICATIONS) }) { Text("Allow notifications (optional)") }
            }

            // microphone picker
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                TextField(
                    value = mics.getOrNull(selectedMic)?.let { "${it.name}${if (it.isWired) " (wired/USB)" else ""}" } ?: "Default microphone",
                    onValueChange = {}, readOnly = true, modifier = Modifier.fillMaxWidth().menuAnchor(),
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                    colors = ExposedDropdownMenuDefaults.textFieldColors(),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    mics.forEachIndexed { i, d ->
                        DropdownMenuItem(text = { Text("${d.name}${if (d.isWired) " (wired/USB)" else ""}") }, onClick = { selectedMic = i; expanded = false })
                    }
                }
            }
            OutlinedButton(onClick = { mics = deviceMonitor.listInputDevices() }) { Text("Refresh devices") }

            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Engine:", color = Color.LightGray)
                val names = listOf("RNNoise (AI)" to ClearVoiceEngine.ENGINE_RNNOISE, "Passthrough" to ClearVoiceEngine.ENGINE_PASSTHROUGH)
                names.forEach { (label, value) ->
                    OutlinedButton(onClick = { engine = value }) {
                        Text(label, color = if (engine == value) ACCENT else Color.LightGray)
                    }
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = monitor, onCheckedChange = { monitor = it })
                Column {
                    Text("Monitor processed audio (headphones!)", color = Color.LightGray)
                    Text("OFF by default — playing the mic through the speaker causes feedback.", color = WARN)
                }
            }

            Button(
                onClick = {
                    if (running) stopService() else startService(engine, monitor, mics.getOrNull(selectedMic)?.id ?: 0)
                    running = !running
                },
                colors = ButtonDefaults.buttonColors(containerColor = if (running) ERR else ACCENT),
                modifier = Modifier.fillMaxWidth(),
                enabled = hasMicPerm,
            ) { Text(if (running) "Stop" else "Start noise suppression") }

            val s = stats
            Text(
                text = buildString {
                    append("Status: ").append(if (s.running) "RUNNING" else "stopped")
                    append("   Engine: ").append(s.engineName.ifEmpty { "—" })
                    append("   In: ").append(s.inRate).append(" Hz")
                    append("\nFrames: ").append(s.framesProcessed)
                    append("   Input: ").append("%.1f dBFS".format(s.inLevelDb))
                    append("   Output: ").append("%.1f dBFS".format(s.outLevelDb))
                    append("   VAD: ").append(if (s.vad >= 0) "%.2f".format(s.vad) else "—")
                    append("\nCPU: ").append("%.1f%%".format(s.cpuPercent))
                    append("   Glitches (overflow/underflow): ").append(s.inOverflow).append("/").append(s.outUnderflow)
                    if (s.fallbackActive) append("\nFALLBACK active (native engine unavailable); NoiseSuppressor supported=").append(s.fallbackSupported)
                },
                color = Color.LightGray,
                modifier = Modifier.background(PANEL).fillMaxWidth().padding(8.dp),
            )
            s.error?.let { Text("Error: $it", color = ERR) }

            Text(
                "Note: a normal Android app cannot replace the system microphone for other apps or cellular calls. " +
                    "This app cleans the mic for in-app monitoring/recording; all processing is local and offline.",
                color = Color.Gray,
            )
            if (!ClearVoiceEngine.nativeAvailable) {
                Text("Native engine failed to load: ${ClearVoiceEngine.loadError}. Using fallback if supported.", color = ERR)
            }
        }
    }

    private fun hasRecordPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun startService(engine: Int, monitor: Boolean, micId: Int) {
        val intent = Intent(this, AudioProcessingService::class.java).apply {
            putExtra(AudioProcessingService.EXTRA_ENGINE, engine)
            putExtra(AudioProcessingService.EXTRA_MONITOR, monitor)
            putExtra(AudioProcessingService.EXTRA_MIC_DEVICE_ID, micId)
        }
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
    }

    private fun stopService() {
        StatsHolder.stop(this)
        stopService(Intent(this, AudioProcessingService::class.java))
    }

    override fun onDestroy() {
        StatsHolder.detach(this)
        super.onDestroy()
    }
}

/** Bridges the service's StateFlow to the UI without binding. */
object StatsHolder {
    private val serviceFlow get() = AudioProcessingServiceHolder.flow
    val flow get() = serviceFlow

    fun attach(context: Context) {
        AudioProcessingServiceHolder.bind(context)
    }

    fun detach(context: Context) {
        AudioProcessingServiceHolder.unbind(context)
    }

    fun stop(context: Context) {
        context.stopService(Intent(context, AudioProcessingService::class.java))
    }
}

/** Holds a reference to the running service instance to expose its stats flow. */
object AudioProcessingServiceHolder {
    @Volatile private var instance: AudioProcessingService? = null
    val flow get() = instance?.stats ?: kotlinx.coroutines.flow.MutableStateFlow(AudioProcessingService.Stats())

    fun bind(context: Context) {
        // The service registers itself in onCreate via this holder.
    }

    fun unbind(context: Context) {}

    fun register(svc: AudioProcessingService) { instance = svc }
    fun unregister(svc: AudioProcessingService) { if (instance === svc) instance = null }
}

@Composable
fun ClearVoiceTheme(content: @Composable () -> Unit) {
    MaterialTheme(content = content)
}
