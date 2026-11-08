#include "test_framework.h"
#include "resampler.h"

#include <cmath>
#include <vector>

using clearvoice::Resampler;

namespace {
constexpr double kPi = 3.14159265358979323846;

std::vector<float> sine(double freq, int rate, size_t n, double amp) {
    std::vector<float> v(n);
    for (size_t i = 0; i < n; ++i) v[i] = static_cast<float>(amp * std::sin(2.0 * kPi * freq * i / rate));
    return v;
}

double snrDb(const std::vector<float>& actual, const std::vector<float>& ideal, size_t skip) {
    double sp = 0.0, ep = 0.0;
    for (size_t i = skip; i < actual.size() && i < ideal.size(); ++i) {
        const double s = ideal[i], e = actual[i] - ideal[i];
        sp += s * s;
        ep += e * e;
    }
    return 10.0 * std::log10(sp / std::max(ep, 1e-30));
}

double rms(const std::vector<float>& v, size_t skip) {
    double p = 0.0;
    for (size_t i = skip; i < v.size(); ++i) p += static_cast<double>(v[i]) * v[i];
    return std::sqrt(p / static_cast<double>(v.size() - skip));
}
} // namespace

TEST(resampler_passthrough_same_rate) {
    Resampler rs(48000, 48000);
    CHECK(rs.passthrough());
    auto in = sine(1000.0, 48000, 960, 0.5);
    std::vector<float> out(960, 0.0f);
    CHECK(rs.process(in.data(), in.size(), out.data(), out.size()) == 960);
    for (size_t i = 0; i < 960; ++i) CHECK(out[i] == in[i]);
}

// The resampler has a fixed group delay: output[n] corresponds to input time
// (n*step - 1), where step = in_rate/out_rate (pos starts at H-1, pend_[p]=x[p-H]).
static std::vector<float> idealDelayed(double freq, double step, int in_rate, size_t m, double amp) {
    std::vector<float> v(m);
    for (size_t i = 0; i < m; ++i)
        v[i] = static_cast<float>(amp * std::sin(2.0 * kPi * freq * (static_cast<double>(i) * step - 1.0) / in_rate));
    return v;
}

TEST(resampler_upsample_44100_to_48000_sine_snr) {
    Resampler rs(44100, 48000);
    const size_t n = 44100; // 1 s
    auto in = sine(1000.0, 44100, n, 0.5);
    std::vector<float> out(n * 48000 / 44100 + 512, 0.0f); // room for ~48000 outputs
    const size_t got = rs.process(in.data(), in.size(), out.data(), out.size());
    CHECK(got > 47900 && got < 48100); // ~48000 samples of output
    const double step = 44100.0 / 48000.0;
    auto ideal = idealDelayed(1000.0, step, 44100, got, 0.5);
    const double s = snrDb(out, ideal, 200);
    std::printf("       [info] upsample 44100->48000: got=%zu SNR=%.2f dB\n", got, s);
    CHECK(s > 60.0); // >60 dB SNR vs analytic ideal
}

TEST(resampler_downsample_48000_to_16000_sine_snr) {
    Resampler rs(48000, 16000);
    const size_t n = 48000; // 1 s
    auto in = sine(1000.0, 48000, n, 0.5);
    std::vector<float> out(n / 3 + 256, 0.0f);
    const size_t got = rs.process(in.data(), in.size(), out.data(), out.size());
    CHECK(got > 15900 && got < 16100);
    auto ideal = idealDelayed(1000.0, 3.0, 48000, got, 0.5);
    const double s = snrDb(out, ideal, 100);
    std::printf("       [info] downsample 48000->16000: got=%zu SNR=%.2f dB\n", got, s);
    CHECK(s > 60.0);
}

TEST(resampler_antialiasing) {
    // 10 kHz tone must be removed when downsampling to 16 kHz (Nyquist = 8 kHz).
    Resampler rs(48000, 16000);
    auto in = sine(10000.0, 48000, 48000, 0.8);
    std::vector<float> out(16000 + 256, 0.0f);
    const size_t got = rs.process(in.data(), in.size(), out.data(), out.size());
    const double inRms = rms(in, 1000);
    const double outRms = rms(out, 1000);
    CHECK(got > 15900);
    CHECK(outRms < inRms * 0.05); // >26 dB attenuation of the aliased tone
}

TEST(resampler_dc_passthrough) {
    Resampler rs(44100, 48000);
    std::vector<float> in(44100, 0.7f);
    std::vector<float> out(48000 + 256, 0.0f);
    const size_t got = rs.process(in.data(), in.size(), out.data(), out.size());
    CHECK(got > 47900);
    double mean = 0.0;
    for (size_t i = 500; i < got; ++i) mean += out[i];
    mean /= static_cast<double>(got - 500);
    CHECK_NEAR(mean, 0.7, 0.01);
}

TEST(resampler_flush_drains_tail) {
    Resampler rs(44100, 48000);
    auto in = sine(440.0, 44100, 4410, 0.3);
    std::vector<float> out(6000, 0.0f);
    size_t got = rs.process(in.data(), in.size(), out.data(), out.size());
    got += rs.flush(out.data() + got, out.size() - got);
    CHECK(got > 4700 && got < 4900); // 4410 * 48000/44100 = 4800
}
