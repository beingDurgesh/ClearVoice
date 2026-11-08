#!/usr/bin/env python3
"""Simulate the exact resampler algorithm in numpy to isolate C bugs vs algorithm issues."""
import numpy as np

H = 24
PHASES = 512
BETA = 8.6

def bessel_i0(x):
    s, t = 1.0, 1.0
    for k in range(1, 64):
        t *= (x / (2 * k)) ** 2
        s += t
        if t < 1e-12 * s:
            break
    return s

def sinc(x):
    return np.sinc(x)  # np.sinc(x) = sin(pi x)/(pi x)

def build_table(in_rate, out_rate):
    ratio = out_rate / in_rate
    fc = 0.5 * min(1.0, ratio) * 0.95
    i0b = bessel_i0(BETA)
    table = np.zeros((PHASES, 2 * H))
    for q in range(PHASES):
        f = q / PHASES
        for k in range(2 * H):
            j = k - H + 1
            d = f - j
            r = d / H
            w = bessel_i0(BETA * np.sqrt(max(0.0, 1 - r * r))) / i0b
            table[q, k] = 2 * fc * sinc(2 * fc * d) * w
    return table, fc

def resample(x, in_rate, out_rate):
    if in_rate == out_rate:
        return x.copy()
    table, fc = build_table(in_rate, out_rate)
    step = in_rate / out_rate
    pend = np.concatenate([np.zeros(H), x])
    pos = float(H - 1)  # first output interpolates at input position H-1 so indices stay >= 0
    out = []
    while True:
        i = int(np.floor(pos))
        if i + H >= len(pend):
            break
        q = int((pos - np.floor(pos)) * PHASES)
        q = min(q, PHASES - 1)
        seg = pend[i - H + 1: i + H + 1]
        out.append(float(np.dot(seg, table[q])))
        pos += step
    return np.array(out)

def snr_db(a, b, skip):
    a, b = a[skip:], b[skip:]
    e = a - b
    return 10 * np.log10(np.sum(b**2) / max(np.sum(e**2), 1e-30))

for in_rate, out_rate, freq in [(44100, 48000, 1000.0), (48000, 16000, 1000.0), (16000, 48000, 500.0)]:
    n = in_rate  # 1 s
    t = np.arange(n) / in_rate
    x = 0.5 * np.sin(2 * np.pi * freq * t)
    y = resample(x, in_rate, out_rate)
    m = len(y)
    step = in_rate / out_rate
    # pend_[p] = x[p - H]; output[n] interpolates pend at pos = (H-1) + n*step,
    # i.e. input time (n*step - 1). Analytic ideal, no shift search:
    ideal = 0.5 * np.sin(2 * np.pi * freq * (np.arange(m) * step - 1) / in_rate)
    s = snr_db(y, ideal, 200)
    print(f"{in_rate}->{out_rate} Hz, {freq} Hz sine: got={m} (expect ~{n*out_rate//in_rate}) SNR={s:.2f} dB (analytic delay)")
