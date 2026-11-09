package com.clearvoice.app.audio

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Holds a reference to the running service instance so the UI can read its
 * stats StateFlow without binding. Lives in the audio package so both the
 * service and MainActivity can use it without cross-package surprises.
 */
object AudioProcessingServiceHolder {
    @Volatile
    private var instance: AudioProcessingService? = null

    val flow: StateFlow<AudioProcessingService.Stats>
        get() = instance?.stats ?: MutableStateFlow(AudioProcessingService.Stats())

    fun register(svc: AudioProcessingService) {
        instance = svc
    }

    fun unregister(svc: AudioProcessingService) {
        if (instance === svc) instance = null
    }
}
