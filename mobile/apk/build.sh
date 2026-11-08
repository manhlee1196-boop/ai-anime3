#!/usr/bin/env bash
# Build APK ở máy có Android SDK (CI dùng .github/workflows/android-apk.yml).
#
#   bash mobile/apk/build.sh              # APK debug
#   APK_OUT=/tmp/anime3.apk bash mobile/apk/build.sh
#
# Cần: python3, node + npm, JDK 17, Android SDK 34 (ANDROID_HOME đã đặt).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APK_DIR="$REPO_DIR/mobile/apk"
OUT="${APK_OUT:-$REPO_DIR/anime3-mobile.apk}"

say() { printf '\n\033[1;35m▸ %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m✘ %s\033[0m\n' "$*" >&2; exit 1; }

command -v node >/dev/null || die "Thiếu node (cần Node 18+)."
command -v python3 >/dev/null || die "Thiếu python3."
[ -n "${ANDROID_HOME:-}" ] || [ -n "${ANDROID_SDK_ROOT:-}" ] \
  || die "Chưa đặt ANDROID_HOME (Android SDK 34)."
java -version 2>&1 | grep -q '"17' || printf '⚠ Java không phải 17 — Capacitor 6 cần JDK 17.\n'

say "Sinh dữ liệu tag (95.939 tag, ~1,4 MB gz)"
(cd "$REPO_DIR" && python3 mobile/build_data.py)

say "Cài Capacitor"
(cd "$APK_DIR" && npm install --no-audit --no-fund)

say "Tạo project Android + chép app"
(cd "$APK_DIR" && [ -d android ] || npx cap add android)
(cd "$APK_DIR" && npx cap sync android)
[ -f "$APK_DIR/android/app/src/main/assets/public/index.html" ] \
  || die "webDir chưa được chép — xem webDir trong capacitor.config.json."
[ -f "$APK_DIR/android/app/src/main/assets/public/data/tags.json" ] \
  || die "Thiếu data/tags.json trong assets — chạy lại mobile/build_data.py."
# AAPT coi *.gz là bản nén của file cùng tên -> "Duplicate resources" với tags.json.
rm -f "$APK_DIR/android/app/src/main/assets/public/data/tags.json.gz"

# Gradle wrapper mặc định chỉ chờ 10 giây; gói gradle-all có thể cần lâu hơn trên mạng chậm.
WRAPPER_PROPERTIES="$APK_DIR/android/gradle/wrapper/gradle-wrapper.properties"
if grep -q '^networkTimeout=' "$WRAPPER_PROPERTIES"; then
  sed -i -E 's/^networkTimeout=.*/networkTimeout=60000/' "$WRAPPER_PROPERTIES"
else
  echo 'networkTimeout=60000' >> "$WRAPPER_PROPERTIES"
fi

say "Build APK"
(cd "$APK_DIR/android" && chmod +x gradlew && ./gradlew assembleDebug --no-daemon)

cp "$APK_DIR/android/app/build/outputs/apk/debug/app-debug.apk" "$OUT"
printf '\n\033[1;32m✔ APK: %s (%s)\033[0m\n' "$OUT" "$(du -h "$OUT" | cut -f1)"
printf 'Cài lên điện thoại: bật "Cài ứng dụng không rõ nguồn gốc" rồi mở file APK.\n'
