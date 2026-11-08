/*
 * Copyright (c) 1996, 2020, Oracle and/or its affiliates. All rights reserved.
 * (OpenJDK jdk17u src/java.base/unix/native/include/jni_md.h — the unix/Android
 *  variant of jni_md.h, needed when cross-compiling JNI code for Android with a
 *  Windows JDK that only ships include/win32.)
 */

#ifndef _JAVASOFT_JNI_MD_H_
#define _JAVASOFT_JNI_MD_H_

#ifndef __has_attribute
  #define __has_attribute(x) 0
#endif

#ifndef JNIEXPORT
  #if (defined(__GNUC__) && ((__GNUC__ > 4) || (__GNUC__ == 4) && (__GNUC_MINOR__ > 2))) || __has_attribute(visibility)
    #ifdef ARM
      #define JNIEXPORT     __attribute__((externally_visible,visibility("default")))
    #else
      #define JNIEXPORT     __attribute__((visibility("default")))
    #endif
  #else
    #define JNIEXPORT
  #endif
#endif

#if (defined(__GNUC__) && ((__GNUC__ > 4) || (__GNUC__ == 4) && (__GNUC_MINOR__ > 2))) || __has_attribute(visibility)
  #ifdef ARM
    #define JNIIMPORT     __attribute__((externally_visible,visibility("default")))
  #else
    #define JNIIMPORT     __attribute__((visibility("default")))
  #endif
#else
  #define JNIIMPORT
#endif

#define JNICALL

typedef int jint;
#ifdef _LP64
typedef long jlong;
#else
typedef long long jlong;
#endif

typedef signed char jbyte;

#endif /* !_JAVASOFT_JNI_MD_H_ */
