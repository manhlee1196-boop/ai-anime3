#!/usr/bin/env bash
# Chép plugin MediaStore vào project Android do Capacitor sinh ra (thư mục được .gitignore).
set -euo pipefail
NATIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APK_DIR="$(cd "$NATIVE_DIR/.." && pwd)"
DEST="$APK_DIR/android/app/src/main/java/vn/anime3/mobile"
[[ -d "$APK_DIR/android/app/src/main" ]] || {
  printf 'Thiếu project Android; chạy npx cap add android trước.\n' >&2
  exit 1
}
mkdir -p "$DEST"
cp "$NATIVE_DIR/MainActivity.java" "$DEST/MainActivity.java"
cp "$NATIVE_DIR/Anime3MediaPlugin.java" "$DEST/Anime3MediaPlugin.java"
grep -q 'registerPlugin(Anime3MediaPlugin.class)' "$DEST/MainActivity.java"
grep -q 'MediaStore.Images.Media.RELATIVE_PATH' "$DEST/Anime3MediaPlugin.java"
printf '✔ Đã cài plugin lưu ảnh Pictures/Anime3.\n'
