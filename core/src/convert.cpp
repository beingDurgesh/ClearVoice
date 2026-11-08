#include "convert.h"

#include <cstdint>

namespace clearvoice {

void convertToMonoF32(float* dst, const void* src, size_t frames, int channels, CvSampleFormat fmt) {
    if (channels <= 0) return;
    if (channels == 1) {
        switch (fmt) {
            case CV_FMT_INT16: {
                const int16_t* s = static_cast<const int16_t*>(src);
                for (size_t i = 0; i < frames; ++i) dst[i] = static_cast<float>(s[i]) / 32768.0f;
                return;
            }
            case CV_FMT_INT32: {
                const int32_t* s = static_cast<const int32_t*>(src);
                for (size_t i = 0; i < frames; ++i) dst[i] = static_cast<float>(s[i] / 2147483648.0);
                return;
            }
            case CV_FMT_FLOAT32: {
                const float* s = static_cast<const float*>(src);
                for (size_t i = 0; i < frames; ++i) dst[i] = s[i];
                return;
            }
        }
        return;
    }
    // Multi-channel: average all channels (standard downmix for a mono mic path).
    const float inv = 1.0f / static_cast<float>(channels);
    for (size_t i = 0; i < frames; ++i) {
        float acc = 0.0f;
        for (int c = 0; c < channels; ++c) {
            const size_t idx = i * static_cast<size_t>(channels) + static_cast<size_t>(c);
            switch (fmt) {
                case CV_FMT_INT16: acc += static_cast<const int16_t*>(src)[idx] / 32768.0f; break;
                case CV_FMT_INT32: acc += static_cast<const int32_t*>(src)[idx] / 2147483648.0f; break;
                case CV_FMT_FLOAT32: acc += static_cast<const float*>(src)[idx]; break;
            }
        }
        dst[i] = acc * inv;
    }
}

} // namespace clearvoice
