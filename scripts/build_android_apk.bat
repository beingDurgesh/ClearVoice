@echo off
rem Build the ClearVoice Android debug APK with the locally installed SDK/NDK/Gradle.
cd "C:\Users\91862\Downloads\Noise Cancellation"
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot
set ANDROID_HOME=%~dp0..\tools\android-sdk
set ANDROID_SDK_ROOT=%ANDROID_HOME%
rem keep gradle's native-lib extraction and caches inside the workspace (sandbox allows it)
set GRADLE_USER_HOME=%~dp0..\tools\gradle-home
rem AGP writes analytics to ~/.android — redirect into the workspace
set ANDROID_USER_HOME=%~dp0..\tools\android-home
set ANDROID_SDK_HOME=%~dp0..\tools\android-home
tools\gradle-8.10.2\bin\gradle.bat -p android --no-daemon assembleDebug
exit /b %errorlevel%
