#include "test_framework.h"

#include <cmath>
#include <cstdint>
#include <vector>

#include "clearvoice/clearvoice.h"

namespace {
struct Noise {
    uint32_t s = 999;
    float next() {
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

TEST(processor_hot_swap_engine_changes_output) {
    // Same input through RNNoise vs Passthrough must differ (RNNoise attenuates noise).
    CvProcessor* p = cv_processor_create(CV_ENGINE_RNNOISE, 48000, 1, 1 << 16);
    CHECK(p != nullptr);
    Noise nz;
    std::vector<int16_t> in(480 * 30);
    for (auto& v : in) v = static_cast<int16_t>(nz.next() * 29000); // loud noise

    auto run = [&](CvEngineType t) {
        CHECK(cv_processor_set_engine(p, t) == CV_OK);
        for (int f = 0; f < 30; ++f)
            CHECK(cv_processor_push(p, in.data() + f * 480, 480, CV_FMT_INT16) == CV_OK);
        size_t avail = cv_processor_out_available(p);
        std::vector<float> out(avail);
        CHECK(cv_processor_read_out(p, out.data(), out.size()) == avail);
        return rms(out);
    };

    const double r_rnnoise = run(CV_ENGINE_RNNOISE);
    const double r_pass = run(CV_ENGINE_PASSTHROUGH);
    const double r_in = rms(std::vector<float>(in.begin(), in.end())) / 32768.0;
    std::printf("       [info] rms in=%.4f rnnoise=%.4f passthrough=%.4f\n", r_in, r_rnnoise, r_pass);
    CHECK(std::string(cv_processor_engine_name(p)) == "Passthrough");
    // passthrough ~ input level; rnnoise must attenuate loud noise clearly
    CHECK(r_pass > r_in * 0.5);
    CHECK(r_rnnoise < r_pass * 0.8);
    // and swapping back works
    CHECK(cv_processor_set_engine(p, CV_ENGINE_RNNOISE) == CV_OK);
    CHECK(std::string(cv_processor_engine_name(p)) == "RNNoise");
    cv_processor_destroy(p);
}

TEST(processor_set_engine_null_arg) {
    CHECK(cv_processor_set_engine(nullptr, CV_ENGINE_RNNOISE) == CV_ERR_INVALID_ARG);
}
