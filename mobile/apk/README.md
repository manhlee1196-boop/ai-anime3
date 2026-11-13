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
bash native/install.sh            # plugin lưu ảnh + callback Colab
cd android && ./gradlew assembleDebug
```

Kết quả: `mobile/apk/android/app/build/outputs/apk/debug/app-debug.apk`.

Trên GitHub thì không phải làm gì thủ công: workflow
[`.github/workflows/android-apk.yml`](../../.github/workflows/android-apk.yml) chạy các
bước trên trong runner có sẵn JDK 17 + Android SDK rồi đăng file APK lên **Artifacts**;
khi push tag `v*` thì gắn luôn vào **Releases** (link tải không cần đăng nhập).

Workflow tự chạy khi push lên nhánh `arena/**` hoặc `main` **và** có thay đổi trong
`mobile/**` (hoặc chính file workflow) — nên push tài liệu không tốn lượt CI. Nút
“Run workflow” chỉ hiện khi file này có trên nhánh mặc định; ở repo này `main` là commit
upload ban đầu (không cùng gốc lịch sử) nên dùng cách push tag / Re-run all jobs.

## Mở Colab và quay lại APK không cần dán link

Tab **🔌 Máy chủ** gọi `Capacitor.Plugins.Browser.open({ url })` để mở notebook Colab
bằng **Custom Tab**: vẫn là ngữ cảnh của app (thanh trên có nút quay lại), nhưng là
trình duyệt thật — nên **đăng nhập Google vẫn được**. Không dùng WebView/iframe cho
Colab vì Google chặn đăng nhập trong WebView (`disallowed_useragent`).

```json
"dependencies": { "@capacitor/browser": "^6.0.4" }
```

1. Trong Custom Tab, người dùng chọn GPU và bấm **Runtime → Run all**.
2. Notebook tạo tunnel rồi hiện **📲 Mở lại Anime3**.
3. Nút dùng `anime3://connect?url=<tunnel>` để trả APK; `Anime3ColabPlugin` nhận URL,
   app ping Forge và tự kết nối. Không có bước copy/dán ở APK mới.

`native/install.sh` chép plugin và đăng ký intent filter `anime3://connect` với
`android:launchMode="singleTask"`, vì vậy callback quay về WebView đang mở thay vì tạo
thêm activity. Plugin chỉ nhận HTTPS `*.gradio.live`/`*.trycloudflare.com`, lưu callback
một lần trong `SharedPreferences`, rồi xoá sau khi JavaScript đọc xong.

- Browser plugin **không bắt buộc để app chạy**: nếu thiếu, `ui.js` tự rơi xuống
  `window.open(url)`. Nhưng trong APK thì `window.open` mở tab ẩn của WebView (dễ mất
  phiên đăng nhập), nên vẫn nên có plugin.
- `npx cap sync android` phải chạy **sau** `npm install` để plugin được chép vào project
  Android (`android/capacitor.settings.gradle`). Workflow đã làm đúng thứ tự.
- PWA và APK cũ không có custom scheme này: vẫn dùng `<tunnel>/vi-mobile/` hoặc clipboard
  như fallback. Xem luồng đầy đủ ở [`../RUN_IN_APP_PLAN.md`](../RUN_IN_APP_PLAN.md).

## Lưu ảnh ra thư viện điện thoại

Nút **💾 Lưu vào máy** ở kết quả/thư viện gọi plugin `Anime3Media` trong `native/`.
Trên Android 10+ plugin ghi bằng MediaStore vào **`Pictures/Anime3`**, đặt `IS_PENDING`
trong lúc ghi rồi publish; ảnh xuất hiện trong Google Photos/Files và app hiện đúng tên
thư mục. Android 9 trở xuống dùng `Android/data/vn.anime3.mobile/files/Pictures/Anime3`,
không xin quyền ghi toàn bộ bộ nhớ. Nút **Chia sẻ** vẫn dùng share sheet khi hệ thống hỗ trợ.

`native/install.sh` chép `MainActivity.java`, `Anime3MediaPlugin.java` và
`Anime3ColabPlugin.java` vào project do Capacitor sinh ra; cả `build.sh` và workflow đều gọi
script này trước khi build. Plugin phải `registerPlugin(...)` **trước** `super.onCreate(...)`
(yêu cầu từ Capacitor 4), nếu không JS không thấy plugin native và app phải báo lỗi rõ thay vì
giả vờ tải qua WebView. Trên PWA, download vẫn do trình duyệt quản lý nên app hướng dẫn kiểm
tra thông báo/Download thay vì khẳng định một đường dẫn cố định.

## Điều cần biết

- **Đừng đóng gói `data/tags.json.gz`**: AAPT coi `*.gz` là "bản nén của file cùng tên"
  nên `tags.json.gz` + `tags.json` bị báo `Duplicate resources` ở task
  `:app:mergeDebugAssets`. `build.sh` và workflow đã `rm` file `.gz` sau `cap sync`
  (APK vốn đã nén zip, bản `.gz` chỉ cần cho đường web `/vi-mobile/`).

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
