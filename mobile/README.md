# 📱 Anime3 Mobile — app tạo ảnh anime cho điện thoại

Giao diện **tối ưu cho màn hình dọc**, chạy trên điện thoại và điều khiển **Forge +
WAI-Illustrious v17** đang chạy trên Google Colab (hoặc máy có GPU của bạn).

> ⚠️ **Điện thoại không tự chạy model.** SDXL 6,5 GB cần GPU 16 GB — điện thoại chỉ là
> **bảng điều khiển**: gõ prompt tiếng Việt, chọn tag, bấm Tạo ảnh, xem tiến trình, huỷ
> job, lưu ảnh. Phần sinh ảnh vẫn ở Colab/PC. Đó cũng là cách mọi app "AI ảnh" trên
> điện thoại hoạt động.

Có **ba cách dùng**, chọn cách nhẹ nhất với bạn:

| Cách | Cần làm gì | Có APK? | Hợp với |
|---|---|---|---|
| **A. Mở `/vi-mobile/`** ⭐ | Không cài gì: mở `<link Forge>/vi-mobile/` trên điện thoại | — | Dùng ngay hôm nay |
| **B. Cài PWA** | Như A, rồi *Thêm vào màn hình chính* | — | Có icon riêng, mở toàn màn hình |
| **C. APK** | GitHub Actions build sẵn file `.apk`, tải về cài | ✅ | Muốn app thật trong danh sách ứng dụng |

---

## A. Dùng ngay: mở `/vi-mobile/` trên điện thoại

Bộ cài Colab đã bật sẵn `--api` và `--cors-allow-origins`, extension **vi-prompt-builder**
tự phục vụ app tại đường dẫn `/vi-mobile/`. Trên điện thoại:

1. Chạy notebook như bình thường, lấy **link public** (gradio.live hoặc trycloudflare).
2. Mở link đó rồi thêm `/vi-mobile/`, ví dụ
   `https://abc123.gradio.live/vi-mobile/`.
3. Dán prompt → **🖼️ Tạo ảnh**. Không cần nhập địa chỉ Forge: app **cùng origin** với
   API nên mặc định đã đúng.

Trong Forge, accordion **“🇻🇳 Prompt tiếng Việt”** ở tab txt2img cũng có link bấm được
tới app điện thoại.

## B. Cài thành app (PWA, không cần APK)

Mở `/vi-mobile/` bằng Chrome trên Android → menu ⋮ → **Thêm vào màn hình chính**
(iPhone/Safari: **Chia sẻ → Thêm vào MH chính**). App có icon riêng, mở toàn màn hình,
và service worker giữ phần giao diện để mở lại nhanh.

## C. APK Android

APK là **vỏ WebView (Capacitor)** bọc đúng giao diện này, có icon trong ngăn kéo ứng dụng.

### C0. Tải bản build sẵn (nhanh nhất, không cần đăng nhập GitHub)

➡️ **[Tải `anime3-mobile.apk` (5,5 MB)](https://github.com/manhlee1196-boop/ai-anime3/releases/download/v1.0.0/anime3-mobile.apk)**
· hoặc mở trang **Releases** của repo.

Cài xong: mở app → **⚙** → dán link Forge (`https://xxxx.gradio.live`) → **Kiểm tra kết nối**.

> **Vì sao không thấy nút “Run workflow” trong tab Actions?** GitHub chỉ hiện nút đó khi
> file workflow có trên **nhánh mặc định (`main`)**. Ở repo này `main` là commit upload
> ban đầu, không cùng gốc lịch sử với hệ thống Colab, nên không merge vào `main`. Thay
> vào đó workflow **tự chạy khi push lên nhánh `arena/**`** (chỉ khi `mobile/**` hoặc
> chính workflow thay đổi) và khi push tag `v*` → gắn APK vào **Releases**. Muốn build
> lại: mở một lần chạy cũ trong tab Actions → **Re-run all jobs**, hoặc push tag mới
> (`git tag v1.0.1 && git push origin v1.0.1`).

### C1. Build bằng GitHub Actions (không cần cài Android SDK)

1. Vào tab **Actions** của repo → workflow **Android APK** → **Run workflow**.
2. Đợi ~5–10 phút, mở lượt chạy vừa xong → tải artifact **anime3-mobile-apk**
   (file `anime3-mobile.apk`).
3. Chuyển file sang điện thoại → bấm để cài → cho phép “Cài ứng dụng không rõ nguồn gốc”.
4. Mở app → bấm **⚙** → dán **địa chỉ Forge** (link tunnel, ví dụ
   `https://abc123.gradio.live`) → **Kiểm tra kết nối** → *Lưu*.

Cũng có thể push tag `v1.0.0` để workflow gắn APK vào GitHub Release.

### C2. Build ở máy có Android SDK

```bash
bash mobile/apk/build.sh                # một lệnh: sinh dữ liệu → cap add/sync → gradlew
# hoặc làm tay:
python3 mobile/build_data.py            # sinh dữ liệu tag (bắt buộc)
cd mobile/apk && npm install
npx cap add android && npx cap sync android
cd android && ./gradlew assembleDebug
# → mobile/apk/android/app/build/outputs/apk/debug/app-debug.apk
```

Yêu cầu: JDK 17, Android SDK 34 (Capacitor 6). Bản `debug` đã được ký bằng keystore
debug nên **cài được ngay**; muốn bản `release` ký chính thức thì tạo keystore và thêm
`signingConfigs` theo hướng dẫn của Capacitor.

APK **không** chứa model và không chứa bản sao của UI: nó đóng gói đúng `mobile/app`
(nên sửa UI là APK nhận thay đổi ở lần build sau) và gọi Forge qua mạng.

> **APK cần CORS.** Trong APK, trang chạy ở `https://localhost` còn API ở domain tunnel —
> khác origin nên Forge phải trả header CORS. Bộ cài đã thêm
> `--cors-allow-origins=*` vào lệnh chạy Forge; nếu bạn tự chạy Forge, thêm cờ đó (hoặc
> `--cors-allow-origins=https://localhost`). Không có cờ này app báo đúng câu
> “Không gọi được máy chủ… phải bật --cors-allow-origins”.

---

## App có gì

| Màn hình | Nội dung |
|---|---|
| **Tạo ảnh** | Prompt + negative (gập lại), thống kê `N tag · M token · mức`, 🧩 **Chuẩn hoá** (thêm tag chất lượng, xếp theo 18 nhóm Illustrious/WAI, khử trùng), ✂️ **Nén** (bỏ tag trùng nghĩa như `eyes` khi đã có `blue_eyes`), chip kích thước + 4 mức phân loại nội dung, tham số nâng cao (seed, steps, CFG, batch, clip skip, hires scale, denoise, hires on/off), nút **Tạo ảnh** + **Huỷ**, tiến trình thật từ `/sdapi/v1/progress` (`⏳ 01:12 · bước 9/25 · 36% · còn ~1m 20s`) |
| **Kho tag** | 95.939 tag phổ biến (mọi tag có nghĩa tiếng Việt đều được giữ, kể cả tag hiếm): gõ **tiếng Việt không cần dấu** (`toc dai` → `long_hair`), lọc theo 18 nhóm, chọn nhiều tag rồi **Chèn vào prompt** |
| **Phong cách** | 12 công thức sẵn (màu nước, cel-shading, ukiyo-e, pixel art…) + đủ **506 tag phong cách** lọc theo nhóm/chất liệu, có nghĩa tiếng Việt |
| **Thư viện** | Ảnh tạo xong **tự lưu trên máy** (IndexedDB, không nằm trong RAM): xem ảnh, chia sẻ/tải về, xoá, **dùng lại prompt + seed** |
| **Cài đặt** | Địa chỉ Forge, tài khoản API (`--api-auth`), tag chất lượng/negative/sampler mặc định, công thức phong cách, cài PWA, xoá thư viện |

Tham số mặc định lấy **nguyên từ `prompt_lib/system_tags.py`** khi sinh dữ liệu
(steps 25, CFG 6, Euler a, clip skip 2, hires 1.5×, denoise 0.4, tag chất lượng kiểu
WAI) — nên app điện thoại và app Gradio gửi payload giống nhau.

## Chạy thử ở máy tính (không cần GPU)

```bash
python3 mobile/build_data.py         # một lần, ~12 giây
python3 mobile/serve.py --mock       # http://127.0.0.1:8787 — Forge giả, có tiến trình + ảnh
python3 mobile/serve.py              # hoặc trỏ Forge thật (mặc định 127.0.0.1:7860)
python3 mobile/serve.py --forge https://abc123.gradio.live --port 8787
```

`serve.py` chuyển tiếp `/sdapi/*` sang Forge, nên mở từ **điện thoại cùng Wi-Fi** bằng
`http://<IP-máy-tính>:8787` là dùng được (địa chỉ IP được in ra khi khởi động). Chế độ
`--mock` dựng Forge giả: tiến trình tăng dần, **Huỷ** hoạt động, trả ảnh PNG gradient —
đủ để kiểm tra toàn bộ giao diện mà không tốn giây GPU nào.

## Kiểm thử

```bash
node mobile/tests/test_core.mjs          # 28 test logic: prompt, payload, token, tìm tag
python3 mobile/tests/test_mobile_assets.py   # 17 test dữ liệu/tài nguyên/id trong HTML
npm i jsdom && node mobile/tests/test_ui_smoke.mjs   # smoke UI thật trên DOM giả + Forge giả
```

`test_core.mjs` chạy payload qua đúng quy ước của `PromptBuilder.payload()`
(`clip_skip → override_settings`, `DPM++ 2M Karras → sampler + scheduler Karras`, bỏ
tham số hires khi tắt hires…) nên sửa một bên mà quên bên kia là test đỏ ngay.

## Cấu trúc thư mục

| File | Việc |
|---|---|
| `app/index.html`, `app/styles.css` | Khung 3 tab + các sheet, CSS mobile (safe-area, nút ≥ 44 px, dark) |
| `app/js/core.js` | Logic thuần: parse tag/trọng số, chuẩn hoá prompt, token, payload, dịch lỗi. **Không DOM** → test được bằng Node |
| `app/js/data.js` | Nạp `tags.json(.gz)`, tìm tag Anh↔Việt, 506 phong cách |
| `app/js/api.js` | Gọi Forge: ping, tiến trình, `txt2img` (POST dài + poll song song), `interrupt` |
| `app/js/store.js` | Cài đặt (localStorage) + ảnh (IndexedDB) |
| `app/js/ui.js` | Nối DOM, 3 tab, sheet Cài đặt/Phong cách/Xem ảnh |
| `app/sw.js`, `app/manifest.webmanifest`, `app/icons/` | PWA: cài ra màn hình chính, mở nhanh khi mạng chập chờn |
| `app/data/tags.json(.gz)` | **Sinh ra**, không commit (`.gitignore`) |
| `build_data.py` | Sinh dữ liệu từ `danbooru_e621.csv`, bản dịch, `style_tags.csv`, `prompt_lib` |
| `make_icons.py` | Vẽ icon PNG bằng stdlib (không cần Pillow) |
| `serve.py` | Server thử + proxy Forge + Forge giả (`--mock`) |
| `apk/` | Vỏ Capacitor (`capacitor.config.json`, `package.json`) để build APK |
| `tests/` | Test Node (logic), test Python (dữ liệu/tài nguyên), smoke UI (jsdom) |

Dữ liệu tag: mọi tag có `post_count ≥ 200` **hoặc** có bản dịch tiếng Việt →
**95.939 tag**, 4,0 MB JSON / **1,36 MB gz**; app tự dùng `DecompressionStream` để đọc
bản gz, máy cũ không hỗ trợ thì tải bản `.json`. Muốn nhẹ hơn:
`python3 mobile/build_data.py --min-count 500` (66.720 tag, 1,04 MB gz).

## Gỡ lỗi nhanh

| Hiện tượng | Nguyên nhân & cách sửa |
|---|---|
| “Không gọi được máy chủ…” | Link tunnel hết hạn (gradio.live sống ~10 phút–vài giờ) → chạy `bash /content/install.sh --status`, rồi `--only launch,verify --restart` và mở **link mới**. Hoặc app ở origin khác mà Forge thiếu `--cors-allow-origins` |
| “Không thấy /sdapi” (404) | Forge chạy thiếu `--api`; bộ cài đã bật sẵn |
| Forge trả 500 / ảnh trắng | Hết VRAM (Hires trên T4): tắt Hires, giảm kích thước, xem `forge.log` |
| Trang `/vi-mobile/` báo thiếu dữ liệu | Chưa sinh dữ liệu: `python3 mobile/build_data.py` (bộ cài chạy tự động ở stage `extras`) |
| Không thấy icon sau khi “Thêm vào MH chính” | Dùng Chrome/Safari (không dùng trình duyệt trong app Facebook/Zalo) |
| Ảnh không lưu vào thư viện | Chế độ ẩn danh chặn IndexedDB — đóng tab ẩn danh, dùng cửa sổ thường |
| APK không cài được | Bật “Cài ứng dụng không rõ nguồn gốc” cho trình quản lý file; APK debug đã ký sẵn |

## Ghi chú kỹ thuật

- **Không có timeout cứng cho việc sinh ảnh**: `POST /sdapi/v1/txt2img` là đồng bộ,
  Forge chỉ trả lời khi xong (Hires trên T4 mất 3–6 phút). App chạy POST và poll
  `/sdapi/v1/progress` song song, nên vẫn thấy tiến trình và huỷ được.
- **Huỷ** gọi `/sdapi/v1/interrupt` rồi bỏ request — không để Forge chạy tiếp một job
  người dùng đã bỏ.
- Ảnh Forge trả về là base64 PNG; app lưu **data URL** vào IndexedDB (không nhét vào
  `localStorage` vì giới hạn ~5 MB).
- Payload theo đúng `prompt_lib/builder.py`: `clip_skip` đi qua
  `override_settings.clip_stop_at_last_layers`, sampler `… Karras` tách thành sampler +
  `scheduler=Karras`, tắt Hires thì bỏ luôn 4 khoá `hr_*`/`denoising_strength`.
