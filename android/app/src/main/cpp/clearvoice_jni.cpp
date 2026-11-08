/* JNI bridge between the Kotlin app and the shared clearvoice core.
 *
 * The same file builds on Android (NDK clang) and on a desktop host (MSVC/clang
 * with a JDK) — it only depends on jni.h and clearvoice.h.
 *
 * All native methods are static and take an opaque jlong handle returned by
 * nativeCreate. Every entry point is wrapped in try/catch and returns an error
 * code instead of throwing across JNI.
 */
#include <jni.h>

#include <cstring>

#include "clearvoice/clearvoice.h"

namespace {

struct EngineHandle {
    CvProcessor* processor = nullptr;
    CvRing* out_ring = 0; // float ring at the OUTPUT rate (48 kHz), drained by nativeReadOut
};

EngineHandle* toHandle(jlong h) { return reinterpret_cast<EngineHandle*>(h); }

// Move processed audio from the processor into the output ring.
inline void drain(EngineHandle* h) {
    if (!h || !h->processor || !h->out_ring) return;
    const size_t avail = cv_processor_out_available(h->processor);
    if (avail == 0) return;
    const size_t n = avail > 4800 ? 4800 : avail;
    float buf[4800];
    const size_t got = cv_processor_read_out(h->processor, buf, n);
    if (got > 0) {
        cv_ring_write(h->out_ring, buf, got);
    }
}

} // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeCreate(JNIEnv* /*env*/, jclass /*clazz*/,
                                                            jint engineType, jint inSampleRate,
                                                            jint inChannels, jint outRingCapacity) {
    try {
        auto* h = new EngineHandle();
        h->processor = cv_processor_create(static_cast<CvEngineType>(engineType), inSampleRate,
                                           inChannels, static_cast<size_t>(outRingCapacity > 0 ? outRingCapacity : 48000 * 2));
        if (!h->processor) {
            delete h;
            return 0;
        }
        // Output ring lives inside the processor's own ring; we expose it via a
        // second ring handle so the RT consumer can zero-pad on underflow.
        h->out_ring = cv_ring_create(static_cast<size_t>(outRingCapacity > 0 ? outRingCapacity : 48000 * 2));
        if (!h->out_ring) {
            cv_processor_destroy(h->processor);
            delete h;
            return 0;
        }
        return reinterpret_cast<jlong>(h);
    } catch (...) {
        return 0;
    }
}

JNIEXPORT void JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeDestroy(JNIEnv* /*env*/, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        if (!h) return;
        if (h->processor) cv_processor_destroy(h->processor);
        if (h->out_ring) cv_ring_destroy(h->out_ring);
        delete h;
    } catch (...) {
    }
}

// Push interleaved int16 PCM (AudioRecord ENCODING_PCM_16BIT).
JNIEXPORT jint JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativePushI16(JNIEnv* env, jclass /*clazz*/, jlong handle,
                                                             jshortArray data, jint frames) {
    try {
        auto* h = toHandle(handle);
        if (!h || !h->processor || !data || frames <= 0) return CV_ERR_INVALID_ARG;
        jshort* p = env->GetShortArrayElements(data, nullptr);
        if (!p) return CV_ERR_OUT_OF_MEMORY;
        const CvError rc = cv_processor_push(h->processor, p, static_cast<size_t>(frames), CV_FMT_INT16);
        env->ReleaseShortArrayElements(data, p, JNI_ABORT);
        // drain processed 48 kHz into the output ring
        drain(h);
        return rc;
    } catch (...) {
        return CV_ERR_ENGINE;
    }
}

// Push interleaved float32 PCM.
JNIEXPORT jint JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativePushF32(JNIEnv* env, jclass /*clazz*/, jlong handle,
                                                             jfloatArray data, jint frames) {
    try {
        auto* h = toHandle(handle);
        if (!h || !h->processor || !data || frames <= 0) return CV_ERR_INVALID_ARG;
        jfloat* p = env->GetFloatArrayElements(data, nullptr);
        if (!p) return CV_ERR_OUT_OF_MEMORY;
        const CvError rc = cv_processor_push(h->processor, p, static_cast<size_t>(frames), CV_FMT_FLOAT32);
        env->ReleaseFloatArrayElements(data, p, JNI_ABORT);
        drain(h);
        return rc;
    } catch (...) {
        return CV_ERR_ENGINE;
    }
}

// Read up to maxSamples processed float32 samples into dst (zero-padded on underflow).
JNIEXPORT jint JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeReadOut(JNIEnv* env, jclass /*clazz*/, jlong handle,
                                                             jfloatArray dst, jint maxSamples) {
    try {
        auto* h = toHandle(handle);
        if (!h || !h->out_ring || !dst || maxSamples <= 0) return 0;
        jfloat* p = env->GetFloatArrayElements(dst, nullptr);
        if (!p) return 0;
        const size_t n = cv_ring_read_padded(h->out_ring, p, static_cast<size_t>(maxSamples));
        env->ReleaseFloatArrayElements(dst, p, 0); // copy back
        return static_cast<jint>(n);
    } catch (...) {
        return 0;
    }
}

JNIEXPORT jint JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeRingAvailable(JNIEnv* /*env*/, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        return h && h->out_ring ? static_cast<jint>(cv_ring_readable(h->out_ring)) : 0;
    } catch (...) {
        return 0;
    }
}

JNIEXPORT jfloat JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeLastVad(JNIEnv* /*env*/, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        return h && h->processor ? cv_processor_last_vad(h->processor) : -1.0f;
    } catch (...) {
        return -1.0f;
    }
}

JNIEXPORT jlong JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeFramesProcessed(JNIEnv* /*env*/, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        return h && h->processor ? static_cast<jlong>(cv_processor_frames_processed(h->processor)) : 0;
    } catch (...) {
        return 0;
    }
}

// Returns long[2] = {outRingOverflow, outRingUnderflow}
JNIEXPORT jlongArray JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeGlitchCounts(JNIEnv* env, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        jlongArray out = env->NewLongArray(2);
        if (!out) return nullptr;
        jlong vals[2] = {0, 0};
        if (h && h->out_ring) {
            vals[0] = static_cast<jlong>(cv_ring_overflow_count(h->out_ring));
            vals[1] = static_cast<jlong>(cv_ring_underflow_count(h->out_ring));
        }
        if (h && h->processor) {
            vals[0] += static_cast<jlong>(cv_processor_out_overflow(h->processor));
        }
        env->SetLongArrayRegion(out, 0, 2, vals);
        return out;
    } catch (...) {
        return nullptr;
    }
}

JNIEXPORT jstring JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeEngineName(JNIEnv* env, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        const char* name = (h && h->processor) ? cv_processor_engine_name(h->processor) : "invalid";
        return env->NewStringUTF(name);
    } catch (...) {
        return env->NewStringUTF("invalid");
    }
}

JNIEXPORT jint JNICALL
Java_com_clearvoice_app_audio_ClearVoiceEngine_nativeInRate(JNIEnv* /*env*/, jclass /*clazz*/, jlong handle) {
    try {
        auto* h = toHandle(handle);
        return h && h->processor ? cv_processor_in_rate(h->processor) : 0;
    } catch (...) {
        return 0;
    }
}

} // extern "C"
