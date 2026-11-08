#pragma once
/* Interleaved PCM/float -> mono float32 conversion. */
#include <cstddef>
#include "clearvoice/clearvoice.h"

namespace clearvoice {

/* Convert `frames` interleaved frames with `channels` channels of format `fmt`
 * into `frames` mono float32 samples in dst (dst must hold >= frames floats). */
void convertToMonoF32(float* dst, const void* src, size_t frames, int channels, CvSampleFormat fmt);

} // namespace clearvoice
