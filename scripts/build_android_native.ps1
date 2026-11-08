# Build libclearvoice_core.so for Android ABIs with the NDK toolchain (no Gradle needed).
$ErrorActionPreference = "Stop"
cd "C:\Users\91862\Downloads\Noise Cancellation"
$cm = "tools\android-sdk\cmake\3.22.1\bin\cmake.exe"
$ndk = "$PWD\tools\android-sdk\ndk\27.3.13750724"
foreach ($abi in @("arm64-v8a", "x86_64")) {
    Write-Host "=== configuring $abi ==="
    & $cm -S android\app\src\main\cpp -B "build\android-$abi" `
        -DCMAKE_TOOLCHAIN_FILE="$ndk\build\cmake\android.toolchain.cmake" `
        -DANDROID_ABI=$abi -DANDROID_PLATFORM=android-24 -DCMAKE_BUILD_TYPE=Release 2>&1 | Select-Object -Last 3
    Write-Host "=== building $abi ==="
    & $cm --build "build\android-$abi" --config Release 2>&1 | Select-Object -Last 6
    Write-Host "$abi exit: $LASTEXITCODE"
}
Get-ChildItem -Recurse build\android-arm64-v8a, build\android-x86_64 -Filter libclearvoice_core.so -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host "SO: $($_.FullName) $($_.Length) bytes" }
