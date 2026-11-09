@echo off
cd "C:\Users\91862\Downloads\Noise Cancellation"
set JH=C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot
set KC=tools\kotlinc\kotlinc\lib\kotlin-compiler.jar
echo using %KC%
"%JH%\bin\java.exe" -cp "%KC%" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler ^
  -cp "tools\android-sdk\platforms\android-35\android.jar;tools\coroutines.jar;tools\core-ktx\classes.jar;tools\core\classes.jar" ^
  -d build\kotlin-check ^
  android\app\src\main\java\com\clearvoice\app\audio\ClearVoiceEngine.kt ^
  android\app\src\main\java\com\clearvoice\app\audio\AudioProcessingService.kt ^
  android\app\src\main\java\com\clearvoice\app\audio\DeviceMonitor.kt ^
  android\app\src\main\java\com\clearvoice\app\audio\NoiseSuppressorFallback.kt ^
  android\app\src\main\java\com\clearvoice\app\audio\ServiceHolder.kt
echo KOTLINC_EXIT=%errorlevel%
