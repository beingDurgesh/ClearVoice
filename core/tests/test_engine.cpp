#include "test_framework.h"
#include "engine.h"

#include <cmath>
#include <memory>
#include <vector>

#include "clearvoice/clearvoice.h"

using clearvoice::IEngine;
using clearvoice::createEngine;

namespace {
// Deterministic pseudo-random noise (LCG), so tests are reproducible.
struct Noise {
    uint32_t s = 12345;
    float next() { // uniform in [-1, 1]
        s = s * 1664525u + 1013904223u;
        return static_cast<float>(s >> 8) / 8388608.0f - 1.0f;
    }
};

double rms(const std::vector<float>& v) {
    double p = 0.0;
    for (float x : v) p += static_cast<double>(x) * x;
    return std::sqrt(p / v.size());
}
} // namespace

TEST(engine_passthrough_identity) {
    std::unique_ptr<IEngine> e(createEngine(CV_ENGINE_PASSTHROUGH));
    CHECK(e != nullptr);
    CHECK(e->frameSize() == 480);
    std::vector<float> in(480), out(480, 0.0f);
    Noise nz;
    for (auto& v : in) v = nz.next() * 0.5f;
    const float vad = e->processFrame(out.data(), in.data());
    for (int i = 0; i < 480; ++i) CHECK(out[i] == in[i]);
    CHECK(vad >= 0.0f && vad <= 1.0f);
}

TEST(engine_rnnoise_frame_size_and_silence) {
    std::unique_ptr<IEngine> e(createEngine(CV_ENGINE_RNNOISE));
    CHECK(e != nullptr);
    CHECK(e->frameSize() == 480); // 10 ms @ 48 kHz
    std::vector<float> in(480, 0.0f), out(480, -9.0f);
    const float vad = e->processFrame(out.data(), in.data());
    CHECK(vad >= 0.0f && vad <= 1.0f);
    for (float v : out) CHECK(std::fabs(v) < 1e-6f);
    CHECK(std::string(e->name()) == "RNNoise");
}

TEST(engine_rnnoise_suppresses_stationary_noise) {
    std::unique_ptr<IEngine> e(createEngine(CV_ENGINE_RNNOISE));
    CHECK(e != nullptr);
    Noise nz;
    double in_rms = 0.0, out_rms = 0.0;
    std::vector<float> in(480), out(480);
    // Loud noise (amp 0.9): below RNNoise's silence threshold (E<0.04) it would
    // pass through by design, so use a realistic level. Verified with the direct
    // upstream probe (tools/debug_rnnoise): settled attenuation ~5.7 dB, vad ~0.01.
    for (int f = 0; f < 30; ++f) {
        for (auto& v : in) v = nz.next() * 0.9f;
        const float vad = e->processFrame(out.data(), in.data());
        CHECK(vad >= 0.0f && vad <= 1.0f);
        CHECK(vad < 0.5f); // white noise must be classified as non-speech
        for (float v : out) CHECK(std::isfinite(v));
        if (f >= 20) {
            in_rms += rms(in) * rms(in);
            out_rms += rms(out) * rms(out);
        }
    }
    in_rms = std::sqrt(in_rms / 10);
    out_rms = std::sqrt(out_rms / 10);
    const double attenDb = 20.0 * std::log10(in_rms / std::max(out_rms, 1e-12));
    std::printf("       [info] white-noise attenuation: %.2f dB (in_rms=%.4f out_rms=%.4f)\n",
                attenDb, in_rms, out_rms);
    // Require at least 2.5 dB suppression (measured ~5.7 dB on this machine).
    CHECK(attenDb > 2.5);
    // And the output must stay bounded (no blow-up).
    CHECK(out_rms < 2.0);
}

TEST(engine_rnnoise_keeps_voice_band_energy) {
    // Speech-like signal: 220 Hz + harmonics with 5 Hz amplitude modulation.
    std::unique_ptr<IEngine> e(createEngine(CV_ENGINE_RNNOISE));
    CHECK(e != nullptr);
    std::vector<float> in(480), out(480);
    double in_rms = 0.0, out_rms = 0.0;
    for (int f = 0; f < 40; ++f) {
        for (int i = 0; i < 480; ++i) {
            const double t = (f * 480 + i) / 48000.0;
            const double env = 0.5 + 0.5 * std::sin(2.0 * 3.14159265 * 5.0 * t);
            in[i] = static_cast<float>(0.4 * env * (std::sin(2.0 * 3.14159265 * 220.0 * t) +
                                                      0.5 * std::sin(2.0 * 3.14159265 * 440.0 * t) +
                                                      0.25 * std::sin(2.0 * 3.14159265 * 880.0 * t)));
        }
        e->processFrame(out.data(), in.data());
        if (f >= 30) {
            in_rms += rms(in) * rms(in);
            out_rms += rms(out) * rms(out);
        }
    }
    in_rms = std::sqrt(in_rms / 10);
    out_rms = std::sqrt(out_rms / 10);
    // Voice-like signal should survive substantially (not be muted to near-zero).
    CHECK(out_rms > in_rms * 0.3);
}

TEST(engine_unknown_type_returns_null) {
    CHECK(createEngine(static_cast<CvEngineType>(99)) == nullptr);
}
