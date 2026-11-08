#include "engine.h"

#include <cmath>
#include <cstring>

#include "rnnoise.h"

namespace clearvoice {

class PassthroughEngine final : public IEngine {
public:
    int frameSize() const override { return CV_SAMPLE_RATE / 100; } // 480 = 10 ms, same as RNNoise
    const char* name() const override { return "Passthrough"; }
    float processFrame(float* out, const float* in) override {
        std::memcpy(out, in, static_cast<size_t>(frameSize()) * sizeof(float));
        return 1.0f; // no VAD available; report "voice" so UI meters keep working
    }
};

class RnNoiseEngine final : public IEngine {
public:
    RnNoiseEngine() : st_(rnnoise_create(nullptr)) {}
    ~RnNoiseEngine() override {
        if (st_) rnnoise_destroy(st_);
    }
    RnNoiseEngine(const RnNoiseEngine&) = delete;
    RnNoiseEngine& operator=(const RnNoiseEngine&) = delete;

    bool valid() const { return st_ != nullptr; }
    int frameSize() const override { return st_ ? rnnoise_get_frame_size() : 0; }
    const char* name() const override { return "RNNoise"; }
    float processFrame(float* out, const float* in) override {
        if (!st_) return -1.0f;
        const float vad = rnnoise_process_frame(st_, out, in);
        // Defensive: never let NaN/inf escape into the audio path.
        const int n = frameSize();
        for (int i = 0; i < n; ++i) {
            if (!std::isfinite(out[i])) out[i] = 0.0f;
        }
        return vad;
    }

private:
    DenoiseState* st_;
};

IEngine* createEngine(CvEngineType type) {
    switch (type) {
        case CV_ENGINE_PASSTHROUGH: return new PassthroughEngine();
        case CV_ENGINE_RNNOISE: {
            auto* e = new RnNoiseEngine();
            if (!e->valid()) {
                delete e;
                return nullptr;
            }
            return e;
        }
    }
    return nullptr;
}

} // namespace clearvoice
