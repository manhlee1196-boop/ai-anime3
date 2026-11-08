# Vỏ APK (Capacitor) cho app điện thoại Anime3

Thư mục này chỉ chứa **vỏ Android**: `capacitor.config.json` trỏ `webDir` vào
`../app` (đúng giao diện đang chạy ở `/vi-mobile/`), nên **không có bản sao thứ hai**
của mã UI. Sửa `mobile/app/**` là APK nhận thay đổi ở lần build sau.

## Build nhanh

```bash
python3 mobile/build_data.py      # bắt buộc: app/data/tags.json(.gz)
cd mobile/apk
npm install
npx cap add android               # sinh thư mục android/ (đã .gitignore)
npx cap sync android              # chép ../app vào android/app/src/main/assets/public
cd android && ./gradlew assembleDebug
```

Kết quả: `mobile/apk/android/app/build/outputs/apk/debug/app-debug.apk`.

Trên GitHub thì không phải làm gì thủ công: workflow
[`.github/workflows/android-apk.yml`](../../.github/workflows/android-apk.yml) chạy các
bước trên trong runner có sẵn JDK 17 + Android SDK rồi đăng file APK lên Artifacts.

## Điều cần biết

- **Yêu cầu**: JDK 17 và Android SDK 34 (Capacitor 6). Capacitor 7+ cần JDK 21 — đừng
  nâng version nếu chưa đổi CI.
- **`webDir` nằm ngoài thư mục project**: `../app`. Giữ nguyên đường dẫn này, nếu không
  APK sẽ đóng gói một bản UI cũ.
- **CORS**: trong APK trang chạy ở `https://localhost`, API ở domain tunnel. Forge phải
  bật `--cors-allow-origins=*` (bộ cài đã thêm) — nếu không app báo đúng câu hướng dẫn
  thay vì im lặng thất bại.
- **`cleartext: true` + `allowMixedContent`**: cho phép dùng Forge trong LAN qua
  `http://192.168.x.x:7860` khi điện thoại cùng Wi-Fi với máy có GPU.
- **APK debug** đã được ký bằng keystore debug → cài trực tiếp được. Muốn phát hành
  chính thức: tạo keystore, thêm `signingConfigs` trong `android/app/build.gradle` và
  build `assembleRelease`.
- **Icon/splash**: Capacitor dùng icon mặc định; muốn đổi thì thay
  `android/app/src/main/res/mipmap-*/ic_launcher*.png` (nguồn: `mobile/app/icons/`).
