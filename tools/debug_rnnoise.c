/* Direct upstream-RNNoise probe: loud noise + speech-like signal, print vad & rms. */
#define _USE_MATH_DEFINES
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include "rnnoise.h"

static unsigned int lcg = 12345;
static float noise(void) {
    lcg = lcg * 1664525u + 1013904223u;
    return (float)(lcg >> 8) / 8388608.0f - 1.0f;
}

int main(void) {
    printf("rnnoise frame size = %d, state size = %d\n", rnnoise_get_frame_size(), rnnoise_get_size());
    DenoiseState* st = rnnoise_create(NULL);
    if (!st) { printf("rnnoise_create FAILED\n"); return 1; }
    int FS = rnnoise_get_frame_size();
    float in[480], out[480];

    printf("--- loud white noise (amp 0.9), 40 frames ---\n");
    double rin = 0, rout = 0;
    for (int f = 0; f < 40; ++f) {
        for (int i = 0; i < FS; ++i) in[i] = noise() * 0.9f;
        float vad = rnnoise_process_frame(st, out, in);
        double ri = 0, ro = 0;
        for (int i = 0; i < FS; ++i) { ri += in[i]*in[i]; ro += out[i]*out[i]; }
        if (f >= 30) { rin += ri; rout += ro; }
        if (f < 3 || f == 39) printf("  frame %2d vad=%.4f rms_in=%.4f rms_out=%.4f\n", f, vad, sqrt(ri/FS), sqrt(ro/FS));
    }
    printf("  settled: rms_in=%.4f rms_out=%.4f atten=%.2f dB\n", sqrt(rin/10/FS), sqrt(rout/10/FS),
           20*log10(sqrt(rin/rout)));

    printf("--- speech-like (220Hz+harmonics, 5Hz AM, amp 0.6), 40 frames ---\n");
    rin = rout = 0;
    for (int f = 0; f < 40; ++f) {
        for (int i = 0; i < FS; ++i) {
            double t = (f * FS + i) / 48000.0;
            double env = 0.5 + 0.5 * sin(2*M_PI*5.0*t);
            in[i] = (float)(0.6 * env * (sin(2*M_PI*220*t) + 0.5*sin(2*M_PI*440*t) + 0.25*sin(2*M_PI*880*t)));
        }
        float vad = rnnoise_process_frame(st, out, in);
        double ri = 0, ro = 0;
        for (int i = 0; i < FS; ++i) { ri += in[i]*in[i]; ro += out[i]*out[i]; }
        if (f >= 30) { rin += ri; rout += ro; }
        if (f < 3 || f == 39) printf("  frame %2d vad=%.4f rms_in=%.4f rms_out=%.4f\n", f, vad, sqrt(ri/FS), sqrt(ro/FS));
    }
    printf("  settled: rms_in=%.4f rms_out=%.4f ratio=%.3f\n", sqrt(rin/10/FS), sqrt(rout/10/FS), sqrt(rout/rin));
    rnnoise_destroy(st);
    return 0;
}
