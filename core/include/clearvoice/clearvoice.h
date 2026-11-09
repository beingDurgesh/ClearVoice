/*
 * ClearVoice core — public C API.
 *
 * One shared library (clearvoice_core.dll on Windows, libclearvoice_core.so on
 * Android) used by the Python/ctypes frontend and the Kotlin/JNI frontend.
 *
 * Threading contract:
 *   - cv_processor_push() and all cv_processor_* setters run on ONE worker thread.
 *   - cv_processor_read_out() / cv_ring_read*() may run on the real-time audio
 *     thread (they only touch the lock-free ring buffer).
 *   - No function allocates on the real-time path except ring/processor creation.
 *   - No C++ exception ever crosses this boundary (all entry points are wrapped).
 */
#ifndef CLEARVOICE_H
#define CLEARVOICE_H

#include <stddef.h>

#if defined(_WIN32)
#  if defined(CV_BUILD_DLL)
#    define CV_API __declspec(dllexport)
#  elif defined(CV_STATIC)
#    define CV_API
#  else
#    define CV_API __declspec(dllimport)
#  endif
#else
#  if defined(CV_BUILD_DLL)
#    define CV_API __attribute__((visibility("default")))
#  else
#    define CV_API
#  endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* The engine always works at 48 kHz mono float32 internally. */
#define CV_SAMPLE_RATE 48000
#define CV_MAX_CHANNELS 8

typedef enum CvEngineType {
    CV_ENGINE_PASSTHROUGH = 0, /* no processing; for A/B testing and fallback */
    CV_ENGINE_RNNOISE = 1      /* RNNoise neural denoiser (default) */
} CvEngineType;

typedef enum CvSampleFormat {
    CV_FMT_INT16 = 0,
    CV_FMT_INT32 = 1,
    CV_FMT_FLOAT32 = 2
} CvSampleFormat;

typedef enum CvError {
    CV_OK = 0,
    CV_ERR_INVALID_ARG = 1,
    CV_ERR_OUT_OF_MEMORY = 2,
    CV_ERR_UNSUPPORTED = 3,
    CV_ERR_ENGINE = 4
} CvError;

/* ---------------- version ---------------- */
CV_API const char* cv_version(void);

/* ---------------- low-level engine (raw frames @ 48 kHz mono float32) ---------------- */
typedef struct CvEngine CvEngine;

CV_API CvEngine* cv_engine_create(CvEngineType type); /* NULL on failure */
CV_API void cv_engine_destroy(CvEngine* e);
CV_API int cv_engine_frame_size(const CvEngine* e); /* samples per frame (RNNoise: 480 = 10 ms) */
CV_API const char* cv_engine_name(const CvEngine* e);
CV_API const char* cv_engine_type_name(CvEngineType type);
/* Process exactly frame_size() samples. Returns voice-activity probability in
 * [0,1] (negative on error). out and in may not alias. */
CV_API float cv_engine_process_frame(CvEngine* e, float* out, const float* in);

/* ---------------- lock-free SPSC ring buffer (float samples) ----------------
 * Single producer, single consumer, no locks. On overflow the NEWEST samples
 * are dropped and counted (never overwrite unread data). */
typedef struct CvRing CvRing;

CV_API CvRing* cv_ring_create(size_t capacity); /* rounded up to pow2; NULL on failure */
CV_API void cv_ring_destroy(CvRing* r);
CV_API size_t cv_ring_write(CvRing* r, const float* src, size_t n); /* returns samples written */
CV_API size_t cv_ring_read(CvRing* r, float* dst, size_t n);        /* returns samples read */
/* Read exactly n samples, zero-filling any shortfall (consumer-side underflow
 * is counted). Use this from the real-time callback. */
CV_API size_t cv_ring_read_padded(CvRing* r, float* dst, size_t n);
CV_API size_t cv_ring_readable(const CvRing* r);
CV_API size_t cv_ring_writable(const CvRing* r);
CV_API unsigned long long cv_ring_overflow_count(const CvRing* r);  /* dropped (producer side) */
CV_API unsigned long long cv_ring_underflow_count(const CvRing* r); /* zero-filled (consumer side) */
CV_API void cv_ring_reset(CvRing* r);

/* ---------------- streaming resampler (windowed-sinc, mono float) ---------------- */
typedef struct CvResampler CvResampler;

CV_API CvResampler* cv_resampler_create(int in_rate, int out_rate); /* NULL on failure; equal rates = passthrough */
CV_API void cv_resampler_destroy(CvResampler* r);
/* Push in_samples @ in_rate, write up to out_capacity @ out_rate; returns written. */
CV_API size_t cv_resampler_process(CvResampler* r, const float* in, size_t in_samples,
                                    float* out, size_t out_capacity);
CV_API size_t cv_resampler_flush(CvResampler* r, float* out, size_t out_capacity); /* drain tail at end of stream (offline use); returns written */
CV_API int cv_resampler_in_rate(const CvResampler* r);
CV_API int cv_resampler_out_rate(const CvResampler* r);

/* ---------------- high-level processor ----------------
 * Pipeline per push: interleaved input -> mono float32 -> resample to 48 kHz ->
 * accumulate into engine-sized frames -> engine -> output ring (48 kHz mono float32). */
typedef struct CvProcessor CvProcessor;

CV_API CvProcessor* cv_processor_create(CvEngineType engine, int in_sample_rate, int in_channels,
                                        size_t out_ring_capacity);
CV_API void cv_processor_destroy(CvProcessor* p);
CV_API CvError cv_processor_push(CvProcessor* p, const void* interleaved, size_t frames, CvSampleFormat fmt);
CV_API size_t cv_processor_read_out(CvProcessor* p, float* dst, size_t max_samples);
CV_API size_t cv_processor_out_available(const CvProcessor* p);
CV_API float cv_processor_last_vad(const CvProcessor* p); /* <0 if no frame processed yet */
CV_API unsigned long long cv_processor_frames_processed(const CvProcessor* p);
CV_API unsigned long long cv_processor_out_overflow(const CvProcessor* p);
CV_API int cv_processor_in_rate(const CvProcessor* p);
CV_API int cv_processor_in_channels(const CvProcessor* p);
CV_API const char* cv_processor_engine_name(const CvProcessor* p);
/* Hot-swap the engine (e.g. suppression ON/OFF while running). Worker thread only.
 * Returns CV_OK on success, CV_ERR_* otherwise. Frame size must match. */
CV_API CvError cv_processor_set_engine(CvProcessor* p, CvEngineType type);
/* Optional high-pass filter before the engine (default OFF). enable=0 disables. */
CV_API CvError cv_processor_set_hpf(CvProcessor* p, int enable, float cutoffHz);

#ifdef __cplusplus
}
#endif

#endif /* CLEARVOICE_H */
