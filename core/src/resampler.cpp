#include "resampler.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace clearvoice {

namespace {
constexpr double kPi = 3.14159265358979323846;

inline double sinc(double x) {
    if (x == 0.0) return 1.0;
    const double px = kPi * x;
    return std::sin(px) / px;
}

// Kaiser window, beta given; I0 = modified Bessel function of the first kind.
double besselI0(double x) {
    double sum = 1.0, term = 1.0;
    for (int k = 1; k < 64; ++k) {
        const double t = x / (2.0 * k);
        term *= t * t;
        sum += term;
        if (term < 1e-12 * sum) break;
    }
    return sum;
}

inline double kaiser(double d, double H, double beta, double i0beta) {
    const double r = d / H; // |r| <= 1
    return besselI0(beta * std::sqrt(std::max(0.0, 1.0 - r * r))) / i0beta;
}
} // namespace

Resampler::Resampler(int in_rate, int out_rate) : in_rate_(in_rate), out_rate_(out_rate) {
    step_ = static_cast<double>(in_rate_) / static_cast<double>(out_rate_);
    // H zeros of "history" + start position H-1, so the first output interpolates
    // at input index H-1 and every tap index (i-H+1 .. i+H) stays >= 0.
    pend_.assign(kHalfTaps, 0.0f);
    pos_ = static_cast<double>(kHalfTaps - 1);
    buildTable();
}

void Resampler::buildTable() {
    const double ratio = static_cast<double>(out_rate_) / static_cast<double>(in_rate_);
    // Normalized cutoff (cycles per input sample), with margin against aliasing.
    const double fc = 0.5 * std::min(1.0, ratio) * 0.95;
    const double beta = 8.6; // ~80 dB stopband attenuation
    const double i0beta = besselI0(beta);
    const int H = kHalfTaps;
    table_.assign(static_cast<size_t>(kPhases) * 2 * H, 0.0f);
    for (int q = 0; q < kPhases; ++q) {
        const double f = static_cast<double>(q) / kPhases; // fractional part of position
        float* row = table_.data() + static_cast<size_t>(q) * 2 * H;
        for (int k = 0; k < 2 * H; ++k) {
            const int j = k - H + 1;          // input tap offset relative to floor(pos)
            const double d = f - j;           // distance from kernel center
            const double h = 2.0 * fc * sinc(2.0 * fc * d) * kaiser(d, H, beta, i0beta);
            row[k] = static_cast<float>(h);
        }
    }
}

size_t Resampler::process(const float* in, size_t in_samples, float* out, size_t out_capacity) {
    if (passthrough()) {
        const size_t n = std::min(in_samples, out_capacity);
        if (n > 0) std::memcpy(out, in, n * sizeof(float));
        return n;
    }
    pend_.insert(pend_.end(), in, in + in_samples);
    return processBuffered(out, out_capacity);
}

size_t Resampler::processBuffered(float* out, size_t out_capacity) {
    const int H = kHalfTaps;
    size_t produced = 0;
    while (produced < out_capacity) {
        const long i = static_cast<long>(std::floor(pos_));
        // Need input indices [i-H+1, i+H]; pend_ starts with H zeros, so i-H+1 >= 0 always.
        if (i + H >= static_cast<long>(pend_.size())) break;
        const int q = static_cast<int>((pos_ - std::floor(pos_)) * kPhases);
        const float* row = table_.data() + static_cast<size_t>(q) * 2 * H;
        const float* x = pend_.data() + (i - H + 1);
        float acc = 0.0f;
        for (int k = 0; k < 2 * H; ++k) acc += x[k] * row[k];
        out[produced++] = acc;
        pos_ += step_;
    }
    // Consume what can no longer be referenced: keep the last H samples as history.
    const long keep_from = static_cast<long>(std::floor(pos_)) - H + 1;
    if (keep_from > 0) {
        pend_.erase(pend_.begin(), pend_.begin() + keep_from);
        pos_ -= static_cast<double>(keep_from);
    }
    return produced;
}

size_t Resampler::flush(float* out, size_t out_capacity) {
    if (passthrough()) return 0;
    // Pad with H zeros so every remaining position can be evaluated, then drain.
    pend_.insert(pend_.end(), kHalfTaps, 0.0f);
    const size_t n = processBuffered(out, out_capacity);
    pend_.assign(kHalfTaps, 0.0f);
    pos_ = static_cast<double>(kHalfTaps - 1);
    return n;
}

} // namespace clearvoice
