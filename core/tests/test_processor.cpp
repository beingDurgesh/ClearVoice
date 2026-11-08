#include "test_framework.h"

#include <cmath>
#include <cstdint>
#include <vector>

#include "clearvoice/clearvoice.h"

namespace {
struct Noise {
    uint32_t s = 777;
    float next() {
        s = s * 1664525u + 1013904223u;
        return static_cast<float>(s >> 8) / 8388608.0f - 1.0f;
    }
};
} // namespace

TEST(processor_passthrough_48k_mono_is_identity) {
    CvProcessor* p = cv_processor_create(CV_ENGINE_PASSTHROUGH, 48000, 1, 16384);
    CHECK(p != nullptr);
    CHECK(cv_processor_in_rate(p) == 48000);
    CHECK(cv_processor_in_channels(p) == 1);
    Noise nz;
    std::vector<float> in(960);
    for (auto& v : in) v = nz.next() * 0.4f;
    CHECK(cv_processor_push(p, in.data(), 960, CV_FMT_FLOAT32) == CV_OK);
    CHECK(cv_processor_frames_processed(p) == 2); // 960 / 480
    std::vector<float> out(960, 0.0f);
    const size_t got = cv_processor_read_out(p, out.data(), out.size());
    CHECK(got == 960);
    for (size_t i = 0; i < 960; ++i) CHECK_NEAR(out[i], in[i], 1e-6);
    CHECK(cv_processor_out_overflow(p) == 0);
    cv_processor_destroy(p);
}

TEST(processor_rnnoise_44k1_stereo_int16_pipeline) {
    CvProcessor* p = cv_processor_create(CV_ENGINE_RNNOISE, 44100, 2, 1 << 16);
    CHECK(p != nullptr);
    CHECK(std::string(cv_processor_engine_name(p)) == "RNNoise");
    Noise nz;
    const size_t frames = 4410; // 0.1 s @ 44.1 kHz
    std::vector<int16_t> in(frames * 2);
    for (auto& v : in) v = static_cast<int16_t>(nz.next() * 16000);
    CHECK(cv_processor_push(p, in.data(), frames, CV_FMT_INT16) == CV_OK);
    // 4410 frames @44.1k -> ~4800 samples @48k -> ~10 RNNoise frames (minus kernel delay)
    CHECK(cv_processor_frames_processed(p) >= 8);
    const size_t avail = cv_processor_out_available(p);
    CHECK(avail >= 8 * 480);
    std::vector<float> out(avail, 0.0f);
    CHECK(cv_processor_read_out(p, out.data(), out.size()) == avail);
    for (float v : out) CHECK(std::isfinite(v));
    const float vad = cv_processor_last_vad(p);
    CHECK(vad >= 0.0f && vad <= 1.0f);
    CHECK(cv_processor_out_overflow(p) == 0); // ring big enough
    cv_processor_destroy(p);
}

TEST(processor_small_blocks_accumulate) {
    // Simulates arbitrary callback block sizes: many small pushes must still
    // produce exactly the right number of output samples.
    CvProcessor* p = cv_processor_create(CV_ENGINE_PASSTHROUGH, 48000, 1, 16384);
    CHECK(p != nullptr);
    Noise nz;
    std::vector<float> all;
    const size_t blocks[] = {13, 7, 512, 1, 300, 480};
    size_t total_in = 0;
    for (size_t b : blocks) {
        std::vector<float> blk(b);
        for (auto& v : blk) v = nz.next() * 0.2f;
        total_in += b;
        CHECK(cv_processor_push(p, blk.data(), b, CV_FMT_FLOAT32) == CV_OK);
        all.insert(all.end(), blk.begin(), blk.end());
    }
    const size_t avail = cv_processor_out_available(p);
    const size_t expect = (total_in / 480) * 480;
    CHECK(avail == expect);
    std::vector<float> out(avail);
    cv_processor_read_out(p, out.data(), out.size());
    for (size_t i = 0; i < avail; ++i) CHECK_NEAR(out[i], all[i], 1e-6);
    cv_processor_destroy(p);
}

TEST(processor_invalid_args) {
    CHECK(cv_processor_create(CV_ENGINE_RNNOISE, 0, 1, 1024) == nullptr);
    CHECK(cv_processor_create(CV_ENGINE_RNNOISE, 48000, 0, 1024) == nullptr);
    CHECK(cv_processor_create(CV_ENGINE_RNNOISE, 48000, CV_MAX_CHANNELS + 1, 1024) == nullptr);
    CvProcessor* p = cv_processor_create(CV_ENGINE_RNNOISE, 48000, 1, 1024);
    CHECK(p != nullptr);
    float dummy[480] = {0};
    CHECK(cv_processor_push(p, nullptr, 480, CV_FMT_FLOAT32) == CV_ERR_INVALID_ARG);
    CHECK(cv_processor_push(p, dummy, 0, CV_FMT_FLOAT32) == CV_ERR_INVALID_ARG);
    CHECK(cv_processor_push(p, dummy, 480, CV_FMT_FLOAT32) == CV_OK);
    cv_processor_destroy(p);
    cv_processor_destroy(nullptr); // must not crash
}
