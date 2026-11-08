#include "processor.h"

#include <algorithm>
#include <cmath>

#include "convert.h"

namespace clearvoice {

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

CvError Processor::push(const void* interleaved, size_t frames, CvSampleFormat fmt) {
    if (!engine_ || !interleaved || frames == 0) return CV_ERR_INVALID_ARG;
    if (in_channels_ <= 0 || in_channels_ > CV_MAX_CHANNELS) return CV_ERR_UNSUPPORTED;

    // 1) format + channel conversion to mono float32 at the input rate
    mono_.resize(frames);
    convertToMonoF32(mono_.data(), interleaved, frames, in_channels_, fmt);

    // 2) resample to 48 kHz (generous bound: ratio * frames + one kernel tail)
    const double ratio = static_cast<double>(CV_SAMPLE_RATE) / static_cast<double>(in_rate_);
    rs_buf_.resize(static_cast<size_t>(frames * ratio) + 2 * Resampler::kHalfTaps + 8);
    const size_t got = resampler_.process(mono_.data(), frames, rs_buf_.data(), rs_buf_.size());

    // 3) accumulate into engine-sized frames and run the engine
    fifo_.push(rs_buf_.data(), got);
    const int fs = engine_->frameSize();
    while (fifo_.size() >= static_cast<size_t>(fs)) {
        fifo_.pop(frame_in_.data(), static_cast<size_t>(fs));
        const float vad = engine_->processFrame(frame_out_.data(), frame_in_.data());
        if (vad >= 0.0f) last_vad_ = vad;
        // 4) to the output ring (drops newest + counts if the consumer is behind)
        out_ring_.write(frame_out_.data(), static_cast<size_t>(fs));
        ++frames_processed_;
    }
    return CV_OK;
}

} // namespace clearvoice
