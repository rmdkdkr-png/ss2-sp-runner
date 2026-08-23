[NGP.emu SS2 — 안드로이드 APK 빌드 인계]

■ 무엇
첨부한 ngpemu-ss2-v0.7-overlay.zip = emu-ex-plus-alpha 포크의 NGP.emu 에 얹을
소스 덮어쓰기 묶음. 롬·세이브스테이트는 들어 있지 않음(금지선).
NGP.emu = 네오지오 포켓 컬러 에뮬레이터. 여기에 『사무라이 스피리츠! 2』용
원버튼 필살기 엔진 + 캐릭터 해설 엔진(15명)이 얹혀 있음.

■ 목표
NgpEmu-release.apk 뽑아서 파일로 전달.

■ 왜 이 방에 넘기나
원래 방은 dl.google.com / maven.google.com 이 전부 막혀 있어 NDK 를 못 받음.
그래서 깃허브 Actions 로만 빌드해 왔고 한 번 고칠 때마다 20~40분 왕복이었음.
이 방은 구글이 열려 있으므로 로컬에서 바로 빌드 가능.

■ 절차

  git clone --depth 1 https://github.com/rmdkdkr-png/emu-ex-plus-alpha.git
  cd emu-ex-plus-alpha
  unzip -o ../ngpemu-ss2-v0.7-overlay.zip        # NGP.emu/ 아래만 덮어씀

  # 1) 시스템 의존물
  sudo apt-get install -y --no-install-recommends autoconf automake autopoint bash \
    gcc-arm-linux-gnueabi file gawk gettext git libtool libtool-bin make nasm \
    pkg-config unzip wget openjdk-21-jdk

  # 2) CMake — 반드시 4.3.x 로 고정
  pip install --break-system-packages cmake==4.3.4
  #  ※ 4.4 이상이면 imagine/cmake/config.cmake 의 CMAKE_EXPERIMENTAL_CXX_IMPORT_STD
  #     UUID(451f2fe2-a8a2-47c3-bc32-94786d8fc91b)가 안 맞아 `import std` 가 꺼지고
  #     imagine / emuframework configure 가 죽음. 이건 확정된 함정임.

  # 3) NDK r30-beta1
  wget https://dl.google.com/android/repository/android-ndk-r30-beta1-linux.zip
  unzip -q android-ndk-r30-beta1-linux.zip && mv android-ndk-r30-beta1 android-ndk

  # 4) Android SDK — **compileSdk 36 이 필요함**
  #    이 방에 미리 깔려 있는 platforms;android-34 / build-tools;34.0.0 로는 부족함.
  #    (imagine/make/gradle/app/build.gradle 이 compileSdk 36, AGP 9.0.0, Gradle 9.4.1)
  sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"

  # 5) 디버그 서명 키 — 없으면 마지막 서명 단계에서 죽음
  mkdir -p ~/.android
  keytool -genkey -v -keystore ~/.android/debug.keystore -storepass android \
    -alias androiddebugkey -keypass android -keyalg RSA -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US"

  # 6) 환경
  export ANDROID_NDK_PATH=$PWD/android-ndk
  export IMAGINE_PATH=$PWD/imagine
  export EMUFRAMEWORK_PATH=$PWD/EmuFramework
  export IMAGINE_SDK_PATH=$PWD/imagine-sdk
  mkdir -p imagine-sdk

  # 7) 번들 라이브러리 + 프레임워크 (여기가 제일 오래 걸림, 20~30분)
  (cd imagine/bundle/all && ./makeAll-android.sh install)
  $IMAGINE_PATH/android.sh config
  $IMAGINE_PATH/android.sh installLinks --config Release
  $EMUFRAMEWORK_PATH/android.sh config
  $EMUFRAMEWORK_PATH/android.sh installLinks --config Release

  # 8) APK
  cd NGP.emu
  make -f android.mk android-apk CONFIG=Release V=1 -j$(nproc)
  # → build/android/build/outputs/apk/release/NgpEmu-release.apk

■ 시간을 줄이고 싶으면
기본값이 armv7 arm64 x86 x86_64 넷을 다 만듦. 폰에 넣어 볼 것뿐이면

  make -f android.mk android-apk CONFIG=Release V=1 android_arch=arm64 -j$(nproc)

로 arm64 하나만. (요즘 폰은 전부 arm64)

■ 이미 검증된 것 (다시 안 해도 됨)
- 바뀐 C/C++ 전부 **리눅스로 실제 빌드**해서 에러 0, 링크까지 확인
- 그 리눅스 빌드를 가상 화면(Xvfb)에 띄워 롬을 물리고 메뉴를 돌아다니며 화면 확인:
  System Options 에 SS2 항목 6개, SS2 Commentator 목록에 한글 15명,
  화면 위 띠에 해설자 초상 + 한글 대사 렌더링 정상
- 대사표(ss2comm_lines.h)·글꼴(ss2comm_font*.h)은 생성 스크립트 출력이고
  기존 헤더와 비트 단위 일치를 확인한 규칙으로 만든 것

■ 걸릴 만한 곳
- `'flat_set' file not found` 류 → clang/libc++ 이 낡음. NDK r30-beta1 을 써야 함
- `archive_entry_crc32` undefined → 시스템 libarchive 를 쓴 것.
  반드시 7번의 `makeAll-android.sh install`(번들 패치본)을 먼저 돌릴 것
- gradle 은 wrapper 가 알아서 받음(9.4.1). AGP 9.0.0
- 첫 빌드는 30~40분. 두 번째부터는 NGP.emu 만 다시 돌면 5분 안쪽

■ 빌드 후 확인해줄 것
1. aapt2 dump badging 으로 package 가 `com.rmdkdkr.ngpemu.ss2` 인지
   (스토어판 com.explusalpha.NgpEmu 와 달라야 나란히 설치됨)
2. APK 안 lib/arm64-v8a/libngpemu.so 에 아래 문자열이 있는지
   `strings` 로: "SS2 Commentator" · "SS2 Commentary Display" · "Band above screen"
   그리고 한글 대사 하나 (예: "겐주로")
3. res/overlays/gpOverlay.png 가 들어갔는지 (해설자 교대 버튼 아이콘)

■ 전달
build/android/build/outputs/apk/release/NgpEmu-release.apk 를 **파일로** 주면 됨.
디버그 서명이면 충분함(개인 설치용).
**깃허브에 푸시할 필요 없음** — 소스는 원래 방에서 관리하고, 여기서는 APK 만 받아 가면 됨.

■ 참고: 이 판(v0.7)에서 바뀐 것
- 해설자 4명 → 15명. 얼굴은 배포물에 없고 사용자 롬에서 실행 중에 뽑음
- 대사 392줄 → 3,700줄, 글리프 486 → 741자
- 해설자 교대 버튼 추가 (말풍선 아이콘 / NgpKey::CommNext)
  Key/Gamepad Input Setup → Commentator, On-screen Input Setup 에서 화면에도 올림
