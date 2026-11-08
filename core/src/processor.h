#pragma once
/* High-level processor: interleaved device audio in -> 48 kHz mono float ring out.
 *
 *   push(): convert -> mono -> resample to 48 kHz -> FrameFifo -> engine frames
 *           -> output ring buffer.
 *   readOut(): called from the real-time thread; drains the output ring.
 *
 * push() runs on a single worker thread; readOut() on a single consumer thread.
 */
#include <memory>
#include <vector>

#include "clearvoice/clearvoice.h"
#include "engine.h"
#include "frame_fifo.h"
#include "resampler.h"
#include "ring_buffer.h"

namespace clearvoice {

class Processor {
public:
    Processor(CvEngineType engine, int in_sample_rate, int in_channels, size_t out_ring_capacity);
    ~Processor() = default;
    Processor(const Processor&) = delete;
    Processor& operator=(const Processor&) = delete;

    bool valid() const { return engine_ != nullptr; }

    CvError push(const void* interleaved, size_t frames, CvSampleFormat fmt);

    size_t readOut(float* dst, size_t max_samples) { return out_ring_.read(dst, max_samples); }
    size_t outAvailable() const { return out_ring_.readable(); }
    float lastVad() const { return last_vad_; }
    unsigned long long framesProcessed() const { return frames_processed_; }
    unsigned long long outOverflow() const { return out_ring_.overflowCount(); }

    int inRate() const { return in_rate_; }
    int inChannels() const { return in_channels_; }
    const char* engineName() const { return engine_ ? engine_->name() : "none"; }
    int engineFrameSize() const { return engine_ ? engine_->frameSize() : 0; }

    RingBuffer& outRing() { return out_ring_; } // for readPadded() from the RT thread

private:
    CvEngineType engine_type_;
    int in_rate_;
    int in_channels_;
    std::unique_ptr<IEngine> engine_;
    Resampler resampler_;
    FrameFifo fifo_;
    RingBuffer out_ring_;
    std::vector<float> mono_;      // scratch: mono float at input rate
    std::vector<float> rs_buf_;    // scratch: resampled 48 kHz
    std::vector<float> frame_in_;  // scratch: one engine frame
    std::vector<float> frame_out_; // scratch: one engine frame
    float last_vad_ = -1.0f;
    unsigned long long frames_processed_ = 0;
};

} // namespace clearvoice
