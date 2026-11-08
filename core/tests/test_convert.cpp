#include "test_framework.h"
#include "convert.h"

#include <cstdint>
#include <vector>

using clearvoice::convertToMonoF32;

TEST(convert_int16_mono) {
    const int16_t in[] = {-32768, 0, 32767};
    float out[3] = {0, 0, 0};
    convertToMonoF32(out, in, 3, 1, CV_FMT_INT16);
    CHECK_NEAR(out[0], -1.0, 1e-6);
    CHECK_NEAR(out[1], 0.0, 1e-6);
    CHECK_NEAR(out[2], 32767.0 / 32768.0, 1e-6);
}

TEST(convert_int16_stereo_downmix) {
    const int16_t in[] = {16384, -16384, 32767, 0}; // 2 frames, 2 ch
    float out[2] = {9, 9};
    convertToMonoF32(out, in, 2, 2, CV_FMT_INT16);
    CHECK_NEAR(out[0], 0.0, 1e-6);                       // (0.5 + -0.5)/2
    CHECK_NEAR(out[1], (32767.0 / 32768.0) / 2, 1e-6);   // (1.0 + 0)/2
}

TEST(convert_int32_mono) {
    const int32_t in[] = {2147483647, -2147483647 - 1};
    float out[2] = {0, 0};
    convertToMonoF32(out, in, 2, 1, CV_FMT_INT32);
    CHECK_NEAR(out[0], 2147483647.0 / 2147483648.0, 1e-6);
    CHECK_NEAR(out[1], -1.0, 1e-6);
}

TEST(convert_float32_passthrough) {
    const float in[] = {0.25f, -0.25f, 1.5f};
    float out[3] = {0, 0, 0};
    convertToMonoF32(out, in, 3, 1, CV_FMT_FLOAT32);
    CHECK(out[0] == 0.25f && out[1] == -0.25f && out[2] == 1.5f);
}

TEST(convert_float32_stereo_downmix) {
    const float in[] = {0.8f, 0.2f};
    float out[1] = {0};
    convertToMonoF32(out, in, 1, 2, CV_FMT_FLOAT32);
    CHECK_NEAR(out[0], 0.5, 1e-6);
}
