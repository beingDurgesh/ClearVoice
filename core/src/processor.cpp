#include "processor.h"

#include <algorithm>
#include <cmath>

namespace {
constexpr double kCvPi = 3.14159265358979323846;
}

#include "convert.h"

namespace clearvoice {

void Processor::Biquad::configureHpf(double freq, double fs) {
    const double w0 = 2.0 * kCvPi * freq / fs;
    const double cw = std::cos(w0), sw = std::sin(w0);
    const double alpha = sw / (2.0 * 0.7071);  // Q = 1/sqrt(2)
    const double a0 = 1.0 + alpha;
    b0 = (1.0 + cw) / 2.0 / a0;
    b1 = -(1.0 + cw) / a0;
    b2 = (1.0 + cw) / 2.0 / a0;
    a1 = -2.0 * cw / a0;
    a2 = (1.0 - alpha) / a0;
    enabled = true;
}

Processor::Processor(CvEngineType engine, int in_sample_rate, int in_channels, size_t out_ring_capacity)
    : engine_type_(engine),
      in_rate_(in_sample_rate),
      in_channels_(in_channels),
      engine_(createEngine(engine)),
      resampler_(in_sample_rate, CV_SAMPLE_RATE),
      out_ring_(out_ring_capacity > 0 ? out_ring_capacity : 16384) {
    if (engine_) {
        const int fs = engine_->frameSize();
        frame_in_.assign(static_cast<size_t>(fs), 0.0f);
        frame_out_.assign(static_cast<size_t>(fs), 0.0f);
    }
}

CvError Processor::setHpf(bool enabled, float cutoffHz) {
    if (cutoffHz < 20.0f || cutoffHz > 2000.0f) return CV_ERR_INVALID_ARG;
    for (auto& h : hpf_) {
        h.enabled = enabled;
        if (enabled) h.configureHpf(cutoffHz, CV_SAMPLE_RATE);
    }
    return CV_OK;
}

CvError Processor::setEngine(CvEngineType type) {
    if (engine_type_ == type && engine_) return CV_OK;
    std::unique_ptr<IEngine> fresh(createEngine(type));
    if (!fresh) return CV_ERR_ENGINE;
    if (engine_ && fresh->frameSize() != engine_->frameSize()) return CV_ERR_UNSUPPORTED;
    engine_ = std::move(fresh);
    engine_type_ = type;
    if (engine_) {
        const int fs = engine_->frameSize();
        frame_in_.assign(static_cast<size_t>(fs), 0.0f);
        frame_out_.assign(static_cast<size_t>(fs), 0.0f);
    }
    last_vad_ = -1.0f;
    return CV_OK;
}

CvError Processor::push(const void* interleaved, size_t frames, CvSampleFormat fmt) {
    if (!engine_ || !interleaved || frames == 0) return CV_ERR_INVALID_ARG;
    if (in_channels_ <= 0 || in_channels_ > CV_MAX_CHANNELS) return CV_ERR_UNSUPPORTED;

    // 1) format + channel conversion to mono float32 at the input rate
    mono_.resize(frames);
    convertToMonoF32(mono_.data(), interleaved, frames, in_channels_, fmt);

    // 2) resample to 48 kHz (generous bound: ratio * frames + one kernel tail)
    const double ratio = static_cast<double>(CV_SAMPLE_RATE) / static_cast<double>(in_rate_);
    rs_buf_.resize(static_cast<size_t>(frames * ratio) + 2 * Resampler::kHalfTaps + 8);
    size_t got = resampler_.process(mono_.data(), frames, rs_buf_.data(), rs_buf_.size());

    // NOTE: the HPF is applied AFTER the engine (on frame_out_), not before it:
    // pre-engine HPF removes low-frequency energy and pushes frames below
    // RNNoise's silence gate (E<0.04), which makes the engine pass everything
    // through (measured: fan SNR collapsed 18.9 -> 4.5 dB). Post-engine HPF
    // removes mains hum without touching the engine's gating.

    // 3) accumulate into engine-sized frames and run the engine
    fifo_.push(rs_buf_.data(), got);
    const int fs = engine_->frameSize();
    while (fifo_.size() >= static_cast<size_t>(fs)) {
        fifo_.pop(frame_in_.data(), static_cast<size_t>(fs));
        const float vad = engine_->processFrame(frame_out_.data(), frame_in_.data());
        if (vad >= 0.0f) last_vad_ = vad;
        // 3b) optional post-engine high-pass (mains hum), applied to the denoised frame
        if (hpf_[0].enabled) {
            for (int i = 0; i < fs; ++i) {
                float v = frame_out_[i];
                for (auto& h : hpf_) v = h.process(v);
                frame_out_[i] = v;
            }
        }
        // 4) to the output ring (drops newest + counts if the consumer is behind)
        out_ring_.write(frame_out_.data(), static_cast<size_t>(fs));
        ++frames_processed_;
    }
    return CV_OK;
}

} // namespace clearvoice
