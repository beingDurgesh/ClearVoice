/* C API wrappers. Every entry point is wrapped in try/catch so no C++ exception
 * ever crosses the FFI boundary (critical for ctypes/JNI stability). */
#include "clearvoice/clearvoice.h"

#include <cstring>

#include "engine.h"
#include "processor.h"
#include "resampler.h"
#include "ring_buffer.h"

#define CV_VERSION_STRING "0.1.0-phase2"

extern "C" {

CV_API const char* cv_version(void) { return CV_VERSION_STRING; }

/* ---------- engine ---------- */
CV_API CvEngine* cv_engine_create(CvEngineType type) {
    try {
        return reinterpret_cast<CvEngine*>(clearvoice::createEngine(type));
    } catch (...) {
        return nullptr;
    }
}

CV_API void cv_engine_destroy(CvEngine* e) {
    try {
        delete reinterpret_cast<clearvoice::IEngine*>(e);
    } catch (...) {
    }
}

CV_API int cv_engine_frame_size(const CvEngine* e) {
    try {
        const auto* eng = reinterpret_cast<const clearvoice::IEngine*>(e);
        return eng ? eng->frameSize() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API const char* cv_engine_name(const CvEngine* e) {
    try {
        const auto* eng = reinterpret_cast<const clearvoice::IEngine*>(e);
        return eng ? eng->name() : "invalid";
    } catch (...) {
        return "invalid";
    }
}

CV_API const char* cv_engine_type_name(CvEngineType type) {
    switch (type) {
        case CV_ENGINE_PASSTHROUGH: return "Passthrough";
        case CV_ENGINE_RNNOISE: return "RNNoise";
    }
    return "Unknown";
}

CV_API float cv_engine_process_frame(CvEngine* e, float* out, const float* in) {
    try {
        auto* eng = reinterpret_cast<clearvoice::IEngine*>(e);
        if (!eng || !out || !in) return -1.0f;
        return eng->processFrame(out, in);
    } catch (...) {
        return -1.0f;
    }
}

/* ---------- ring buffer ---------- */
CV_API CvRing* cv_ring_create(size_t capacity) {
    try {
        return reinterpret_cast<CvRing*>(new clearvoice::RingBuffer(capacity));
    } catch (...) {
        return nullptr;
    }
}

CV_API void cv_ring_destroy(CvRing* r) {
    try {
        delete reinterpret_cast<clearvoice::RingBuffer*>(r);
    } catch (...) {
    }
}

CV_API size_t cv_ring_write(CvRing* r, const float* src, size_t n) {
    try {
        auto* rb = reinterpret_cast<clearvoice::RingBuffer*>(r);
        if (!rb || (!src && n > 0)) return 0;
        return rb->write(src, n);
    } catch (...) {
        return 0;
    }
}

CV_API size_t cv_ring_read(CvRing* r, float* dst, size_t n) {
    try {
        auto* rb = reinterpret_cast<clearvoice::RingBuffer*>(r);
        if (!rb || (!dst && n > 0)) return 0;
        return rb->read(dst, n);
    } catch (...) {
        return 0;
    }
}

CV_API size_t cv_ring_read_padded(CvRing* r, float* dst, size_t n) {
    try {
        auto* rb = reinterpret_cast<clearvoice::RingBuffer*>(r);
        if (!rb || (!dst && n > 0)) return 0;
        return rb->readPadded(dst, n);
    } catch (...) {
        return 0;
    }
}

CV_API size_t cv_ring_readable(const CvRing* r) {
    try {
        const auto* rb = reinterpret_cast<const clearvoice::RingBuffer*>(r);
        return rb ? rb->readable() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API size_t cv_ring_writable(const CvRing* r) {
    try {
        const auto* rb = reinterpret_cast<const clearvoice::RingBuffer*>(r);
        return rb ? rb->writable() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API unsigned long long cv_ring_overflow_count(const CvRing* r) {
    try {
        const auto* rb = reinterpret_cast<const clearvoice::RingBuffer*>(r);
        return rb ? rb->overflowCount() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API unsigned long long cv_ring_underflow_count(const CvRing* r) {
    try {
        const auto* rb = reinterpret_cast<const clearvoice::RingBuffer*>(r);
        return rb ? rb->underflowCount() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API void cv_ring_reset(CvRing* r) {
    try {
        if (auto* rb = reinterpret_cast<clearvoice::RingBuffer*>(r)) rb->reset();
    } catch (...) {
    }
}

/* ---------- resampler ---------- */
CV_API CvResampler* cv_resampler_create(int in_rate, int out_rate) {
    try {
        if (in_rate <= 0 || out_rate <= 0) return nullptr;
        return reinterpret_cast<CvResampler*>(new clearvoice::Resampler(in_rate, out_rate));
    } catch (...) {
        return nullptr;
    }
}

CV_API void cv_resampler_destroy(CvResampler* r) {
    try {
        delete reinterpret_cast<clearvoice::Resampler*>(r);
    } catch (...) {
    }
}

CV_API size_t cv_resampler_process(CvResampler* r, const float* in, size_t in_samples, float* out, size_t out_capacity) {
    try {
        auto* rs = reinterpret_cast<clearvoice::Resampler*>(r);
        if (!rs || (!in && in_samples > 0) || (!out && out_capacity > 0)) return 0;
        return rs->process(in, in_samples, out, out_capacity);
    } catch (...) {
        return 0;
    }
}

CV_API size_t cv_resampler_flush(CvResampler* r, float* out, size_t out_capacity) {
    try {
        auto* rs = reinterpret_cast<clearvoice::Resampler*>(r);
        if (!rs || (!out && out_capacity > 0)) return 0;
        return rs->flush(out, out_capacity);
    } catch (...) {
        return 0;
    }
}

CV_API int cv_resampler_in_rate(const CvResampler* r) {
    try {
        const auto* rs = reinterpret_cast<const clearvoice::Resampler*>(r);
        return rs ? rs->inRate() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API int cv_resampler_out_rate(const CvResampler* r) {
    try {
        const auto* rs = reinterpret_cast<const clearvoice::Resampler*>(r);
        return rs ? rs->outRate() : 0;
    } catch (...) {
        return 0;
    }
}

/* ---------- processor ---------- */
CV_API CvProcessor* cv_processor_create(CvEngineType engine, int in_sample_rate, int in_channels,
                                        size_t out_ring_capacity) {
    try {
        if (in_sample_rate <= 0 || in_channels <= 0 || in_channels > CV_MAX_CHANNELS) return nullptr;
        auto* p = new clearvoice::Processor(engine, in_sample_rate, in_channels, out_ring_capacity);
        if (!p->valid()) {
            delete p;
            return nullptr;
        }
        return reinterpret_cast<CvProcessor*>(p);
    } catch (...) {
        return nullptr;
    }
}

CV_API void cv_processor_destroy(CvProcessor* p) {
    try {
        delete reinterpret_cast<clearvoice::Processor*>(p);
    } catch (...) {
    }
}

CV_API CvError cv_processor_push(CvProcessor* p, const void* interleaved, size_t frames, CvSampleFormat fmt) {
    try {
        auto* proc = reinterpret_cast<clearvoice::Processor*>(p);
        if (!proc) return CV_ERR_INVALID_ARG;
        return proc->push(interleaved, frames, fmt);
    } catch (...) {
        return CV_ERR_ENGINE;
    }
}

CV_API size_t cv_processor_read_out(CvProcessor* p, float* dst, size_t max_samples) {
    try {
        auto* proc = reinterpret_cast<clearvoice::Processor*>(p);
        if (!proc || (!dst && max_samples > 0)) return 0;
        return proc->readOut(dst, max_samples);
    } catch (...) {
        return 0;
    }
}

CV_API size_t cv_processor_out_available(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->outAvailable() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API float cv_processor_last_vad(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->lastVad() : -1.0f;
    } catch (...) {
        return -1.0f;
    }
}

CV_API unsigned long long cv_processor_frames_processed(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->framesProcessed() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API unsigned long long cv_processor_out_overflow(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->outOverflow() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API int cv_processor_in_rate(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->inRate() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API int cv_processor_in_channels(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->inChannels() : 0;
    } catch (...) {
        return 0;
    }
}

CV_API CvError cv_processor_set_engine(CvProcessor* p, CvEngineType type) {
    try {
        auto* proc = reinterpret_cast<clearvoice::Processor*>(p);
        if (!proc) return CV_ERR_INVALID_ARG;
        return proc->setEngine(type);
    } catch (...) {
        return CV_ERR_ENGINE;
    }
}

CV_API const char* cv_processor_engine_name(const CvProcessor* p) {
    try {
        const auto* proc = reinterpret_cast<const clearvoice::Processor*>(p);
        return proc ? proc->engineName() : "invalid";
    } catch (...) {
        return "invalid";
    }
}

} // extern "C"
