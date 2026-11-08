#pragma once
/* Noise-suppression engine interface. One engine = one fixed-size frame at
 * 48 kHz mono float32. Implementations must be cheap and allocation-free in
 * processFrame() (it runs on the worker thread once per 10 ms). */
#include "clearvoice/clearvoice.h"

namespace clearvoice {

class IEngine {
public:
    virtual ~IEngine() = default;
    virtual int frameSize() const = 0;
    virtual const char* name() const = 0;
    /* Process one frame; returns voice-activity probability in [0,1] or <0 on error. */
    virtual float processFrame(float* out, const float* in) = 0;
};

IEngine* createEngine(CvEngineType type); // nullptr if type unknown

} // namespace clearvoice
