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
cp "$NATIVE_DIR/Anime3ColabPlugin.java" "$DEST/Anime3ColabPlugin.java"
grep -q 'registerPlugin(Anime3MediaPlugin.class)' "$DEST/MainActivity.java"
grep -q 'registerPlugin(Anime3ColabPlugin.class)' "$DEST/MainActivity.java"
grep -q 'MediaStore.Images.Media.RELATIVE_PATH' "$DEST/Anime3MediaPlugin.java"
grep -q 'anime3://connect' "$DEST/Anime3ColabPlugin.java"

# Capacitor sinh AndroidManifest khi `cap add android`; cập nhật idempotent sau mỗi
# `cap sync`. singleTask trả custom scheme vào WebView có sẵn thay vì mở app lần hai.
MANIFEST="$APK_DIR/android/app/src/main/AndroidManifest.xml"
python3 - "$MANIFEST" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
pattern = re.compile(
    r'(<activity\b(?=[^>]*\bandroid:name="(?:\.MainActivity|vn\.anime3\.mobile\.MainActivity)")[^>]*)(>)(.*?)(</activity>)',
    re.S,
)
match = pattern.search(text)
if not match:
    raise SystemExit("Không tìm thấy MainActivity trong AndroidManifest.xml")
opening, end, body, closing = match.groups()
if not re.search(r'\bandroid:launchMode=', opening):
    opening += ' android:launchMode="singleTask"'
if "Anime3 Colab direct callback" not in body:
    body += '''
        <!-- Anime3 Colab direct callback: notebook mở anime3://connect?url=... -->
        <intent-filter>
            <action android:name="android.intent.action.VIEW" />
            <category android:name="android.intent.category.DEFAULT" />
            <category android:name="android.intent.category.BROWSABLE" />
            <data android:scheme="anime3" android:host="connect" />
        </intent-filter>
'''
text = text[:match.start()] + opening + end + body + closing + text[match.end():]
path.write_text(text, encoding="utf-8")
PY
grep -q 'android:scheme="anime3"' "$MANIFEST"
grep -q 'android:launchMode="singleTask"' "$MANIFEST"
printf '✔ Đã cài plugin lưu ảnh và callback Colab anime3://connect.\n'
