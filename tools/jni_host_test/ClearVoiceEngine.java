package com.clearvoice.app.audio;

/**
 * Host-side stub of the Android engine class, used to verify the JNI bridge
 * (clearvoice_jni.cpp) on a desktop JVM without an Android device.
 *
 * The class name/package MUST match the Android class so the JNI function
 * names in clearvoice_jni.cpp resolve. Run:
 *   java -cp classes com.clearvoice.app.audio.ClearVoiceEngine <path-to-dll>
 */
public class ClearVoiceEngine {

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: ClearVoiceEngine <absolute-path-to-jni-dll>");
            System.exit(2);
        }
        System.load(new java.io.File(args[0]).getAbsolutePath());

        long h = nativeCreate(1 /*RNNOISE*/, 44100, 2, 48000 * 2);
        if (h == 0) {
            System.out.println("FAIL: nativeCreate returned 0");
            System.exit(1);
        }
        System.out.println("engine=" + nativeEngineName(h) + " inRate=" + nativeInRate(h));

        // deterministic noise, stereo int16 @ 44.1 kHz
        java.util.Random rng = new java.util.Random(42);
        int blockFrames = 512;
        short[] block = new short[blockFrames * 2];
        float[] out = new float[blockFrames * 4];
        int totalOut = 0;
        double outSq = 0;
        int blocks = 20;
        for (int b = 0; b < blocks; b++) {
            for (int i = 0; i < block.length; i++) block[i] = (short) (rng.nextGaussian() * 12000);
            int rc = nativePushI16(h, block, blockFrames);
            if (rc != 0) {
                System.out.println("FAIL: nativePushI16 rc=" + rc);
                System.exit(1);
            }
            int got = nativeReadOut(h, out, out.length);
            for (int i = 0; i < got; i++) { outSq += (double) out[i] * out[i]; }
            totalOut += got;
        }
        long frames = nativeFramesProcessed(h);
        float vad = nativeLastVad(h);
        long[] glitches = nativeGlitchCounts(h);
        System.out.printf("blocks=%d totalOut=%d framesProcessed=%d vad=%.4f overflow=%d underflow=%d%n",
                blocks, totalOut, frames, vad, glitches[0], glitches[1]);
        double rms = Math.sqrt(outSq / Math.max(1, totalOut));
        System.out.printf("outRms=%.5f%n", rms);

        nativeDestroy(h);

        boolean ok = frames >= 15 && totalOut > 0 && vad >= 0f && vad <= 1f && glitches[0] == 0;
        System.out.println(ok ? "JNI HOST TEST: OK" : "JNI HOST TEST: FAILED");
        System.exit(ok ? 0 : 1);
    }

    public static native long nativeCreate(int engineType, int inSampleRate, int inChannels, int outRingCapacity);
    public static native void nativeDestroy(long handle);
    public static native int nativePushI16(long handle, short[] samples, int frames);
    public static native int nativePushF32(long handle, float[] samples, int frames);
    public static native int nativeReadOut(long handle, float[] dst, int maxSamples);
    public static native int nativeAvailable(long handle);
    public static native float nativeLastVad(long handle);
    public static native long nativeFramesProcessed(long handle);
    public static native long[] nativeGlitchCounts(long handle);
    public static native String nativeEngineName(long handle);
    public static native int nativeInRate(long handle);
}
