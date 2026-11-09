#include "test_framework.h"

#include <cmath>
#include <vector>

#include "clearvoice/clearvoice.h"

namespace {
std::vector<float> sine(double freq, int rate, int n, double amp) {
    std::vector<float> v(n);
    for (int i = 0; i < n; ++i) v[i] = static_cast<float>(amp * std::sin(2.0 * 3.14159265358979 * freq * i / rate));
    return v;
}
double rmsFrom(const std::vector<float>& v, size_t skip) {
    double p = 0;
    for (size_t i = skip; i < v.size(); ++i) p += (double)v[i] * v[i];
    return std::sqrt(p / (v.size() - skip));
}
} // namespace

TEST(processor_hpf_removes_50hz_keeps_1khz) {
    CvProcessor* p = cv_processor_create(CV_ENGINE_PASSTHROUGH, 48000, 1, 1 << 16);
    CHECK(p != nullptr);
    CHECK(cv_processor_set_hpf(p, 1, 80.0f) == CV_OK);

    auto run = [&](double freq) {
        auto in = sine(freq, 48000, 48000, 0.5);  // 1 s
        for (int off = 0; off < 48000; off += 480)
            CHECK(cv_processor_push(p, in.data() + off, 480, CV_FMT_FLOAT32) == CV_OK);
        size_t avail = cv_processor_out_available(p);
        std::vector<float> out(avail);
        cv_processor_read_out(p, out.data(), out.size());
        return rmsFrom(out, 24000) / rmsFrom(in, 24000);  // settled gain
    };

    const double g50 = run(50.0);
    const double g1k = run(1000.0);
    std::printf("       [info] HPF@80Hz gain: 50Hz=%.4f (%.1f dB), 1kHz=%.4f (%.2f dB)\n",
                g50, 20 * std::log10(g50), g1k, 20 * std::log10(g1k));
    CHECK(g50 < 0.2);   // 50 Hz removed by >14 dB (4th-order @ 80 Hz)
    CHECK(g1k > 0.95);  // 1 kHz essentially untouched

    // disable -> passthrough again
    CHECK(cv_processor_set_hpf(p, 0, 80.0f) == CV_OK);
    const double g50off = run(50.0);
    CHECK(g50off > 0.9);
    CHECK(cv_processor_set_hpf(p, 1, 5.0f) == CV_ERR_INVALID_ARG);  // out of range
    cv_processor_destroy(p);
}
