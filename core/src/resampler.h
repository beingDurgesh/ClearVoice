#pragma once
/* Streaming sample-rate converter, mono float32.
 *
 * Design: table-driven windowed-sinc interpolation.
 *  - Kernel half-width H taps on the INPUT side, Kaiser window (beta ~ 8.6).
 *  - PHASES fractional-phase table entries, so each output sample is a dot
 *    product of 2H input samples with a precomputed kernel — no transcendental
 *    functions in the real-time loop.
 *  - Anti-aliasing cutoff: fc = 0.5 * min(1, out_rate/in_rate) * 0.95 of the
 *    input Nyquist, so downsampling cannot alias.
 *  - Latency: H input samples of lookahead (H=24 @ any rate ~ 0.5 ms).
 * Single-threaded use.
 */
#include <cstddef>
#include <vector>

namespace clearvoice {

class Resampler {
public:
    Resampler(int in_rate, int out_rate);
    ~Resampler() = default;
    Resampler(const Resampler&) = delete;
    Resampler& operator=(const Resampler&) = delete;

    /* Push in_samples @ in_rate; write up to out_capacity @ out_rate. Returns written. */
    size_t process(const float* in, size_t in_samples, float* out, size_t out_capacity);
    /* Append zero padding and emit everything that can be emitted (end of stream). */
    size_t flush(float* out, size_t out_capacity);

    int inRate() const { return in_rate_; }
    int outRate() const { return out_rate_; }
    bool passthrough() const { return in_rate_ == out_rate_; }

    static constexpr int kHalfTaps = 24;   // H
    static constexpr int kPhases = 512;    // fractional-phase table resolution

private:
    void buildTable();
    size_t processBuffered(float* out, size_t out_capacity); // core loop over pend_

    int in_rate_;
    int out_rate_;
    double step_;        // input samples per output sample = in/out
    double pos_ = 0.0;   // position of next output sample, in pend_ coordinates
    std::vector<float> pend_;                 // unconsumed input (starts with kHalfTaps zeros)
    std::vector<float> table_;                // kPhases * 2*kHalfTaps kernel values
};

} // namespace clearvoice
