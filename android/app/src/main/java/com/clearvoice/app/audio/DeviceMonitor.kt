package com.clearvoice.app.audio

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.AudioDeviceCallback

/** Lists input (microphone) devices and reports plug/unplug changes. */
class DeviceMonitor(private val context: Context) {

    data class MicDevice(val id: Int, val name: String, val type: Int, val isWired: Boolean)

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    fun listInputDevices(): List<MicDevice> {
        return try {
            audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS).map { d ->
                MicDevice(
                    id = d.id,
                    name = d.productName?.toString() ?: "Unknown mic",
                    type = d.type,
                    isWired = d.type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
                        d.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES ||
                        d.type == AudioDeviceInfo.TYPE_USB_DEVICE ||
                        d.type == AudioDeviceInfo.TYPE_USB_HEADSET ||
                        d.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO,
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun registerCallback(onChanged: () -> Unit): AudioDeviceCallback {
        val cb = object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(added: Array<out AudioDeviceInfo>?) = onChanged()
            override fun onAudioDevicesRemoved(removed: Array<out AudioDeviceInfo>?) = onChanged()
        }
        audioManager.registerAudioDeviceCallback(cb, null)
        return cb
    }

    fun unregisterCallback(cb: AudioDeviceCallback) {
        audioManager.unregisterAudioDeviceCallback(cb)
    }
}
