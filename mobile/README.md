# 📱 Anime3 Mobile — app tạo ảnh anime cho điện thoại

Giao diện **tối ưu cho màn hình dọc**, chạy trên điện thoại và điều khiển **Forge +
WAI-Illustrious v17** đang chạy trên Google Colab (hoặc máy có GPU của bạn).

> ⚠️ **Điện thoại không tự chạy model.** SDXL 6,5 GB cần GPU 16 GB — điện thoại chỉ là
> **bảng điều khiển**: gõ prompt tiếng Việt, chọn tag, bấm Tạo ảnh, xem tiến trình, huỷ
> job, lưu ảnh. Phần sinh ảnh vẫn ở Colab/PC. Đó cũng là cách mọi app "AI ảnh" trên
> điện thoại hoạt động.

Có **ba cách cài**, chọn cách nhẹ nhất với bạn — cả ba đều có tab **🔌 Máy chủ** để
mở Colab và tự bắt link Forge ngay trong app:

| Cách | Cần làm gì | Có APK? | Hợp với |
|---|---|---|---|
| **A. Mở `/vi-mobile/`** ⭐ | Không cài gì: mở `<link Forge>/vi-mobile/` trên điện thoại | — | Dùng ngay hôm nay |
| **B. Cài PWA** | Như A, rồi *Thêm vào màn hình chính* | — | Có icon riêng, mở toàn màn hình |
| **C. APK** ⭐ | GitHub Actions build sẵn file `.apk`, tải về cài | ✅ | Muốn app thật trong danh sách ứng dụng |

Bấm **🔌 Máy chủ → Mở Colab & chạy** là Colab mở ngay từ app (tab trình duyệt gắn với
app, có nút quay lại); chạy *Run all* xong thì **quay lại app là app tự đọc link Forge
trong clipboard và kết nối** — không phải copy tay (xem [mục D](#d-chạy-colab-ngay-trong-app-tab--máy-chủ)).

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

➡️ **[Tải `anime3-mobile.apk` (v1.1.0)](https://github.com/manhlee1196-boop/ai-anime3/releases/download/v1.1.0/anime3-mobile.apk)**
· hoặc mở trang **Releases** của repo.

Cài xong: mở app → tab **🔌 Máy chủ** → **Mở Colab & chạy** → *Run all* → quay lại app
(app tự nhận link). Không muốn dùng Colab thì dán link Forge vào ô địa chỉ → **Kết nối**.

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
4. Mở app → tab **🔌 Máy chủ** → **Mở Colab & chạy** (hoặc dán link tunnel, ví dụ
   `https://abc123.gradio.live`, rồi **Kết nối**).

Cũng có thể push tag `v1.1.0` để workflow gắn APK vào GitHub Release.

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

## D. Chạy Colab ngay trong app (tab 🔌 Máy chủ)

Mục tiêu: **không phải chép link bằng tay**. App không nhúng Colab (xem lý do bên dưới)
mà mở Colab ở **Custom Tab** — vẫn nằm trong app, có nút quay lại — rồi **tự bắt link
tunnel** khi bạn quay về.

| Nút | Việc nó làm |
|---|---|
| **🚀 Mở Colab & chạy** | Mở đúng notebook `colab/WAI_v17_1click.ipynb` của repo trên Colab (Custom Tab trong APK, tab mới trên web). Bấm *Runtime → Run all* là Forge cài + chạy + in link public |
| *(tự động)* **nhận link khi quay lại** | Quay lại app → app đọc clipboard → thấy `*.gradio.live` / `*.trycloudflare.com` / `*.ngrok*` → kết nối luôn. Tắt được bằng công tắc **Tự nhận link khi quay lại app** |
| **📋 Dán link trong clipboard** | Đọc clipboard theo yêu cầu, tự tìm link Forge trong cả đoạn log Colab (kể cả log cloudflared) rồi kết nối |
| **🔗 Kết nối** + ô địa chỉ | Dán tay `https://xxxx.gradio.live` hoặc `192.168.1.9:7860` (Forge trong LAN, tự hiểu là `http`) |
| **📄 Copy lệnh kiểm tra** | Copy `bash /content/install.sh --status` để dán vào Colab khi không thấy link |
| **♻️ Copy lệnh lấy link mới** | Copy `bash /content/install.sh --only launch,verify --restart` — link gradio.live hết hạn thì chạy lệnh này, link mới hiện ra, quay lại app là tự nhận |
| **🩺 Chẩn đoán kết nối** | Gọi song song 6 endpoint (`options`, `cmd-flags`, `sd-models`, `progress`, `internal/progress`, `vi-mobile/api/health`) bằng đúng GET/POST; kiểm tra cả API ảnh nén cho Android |
| **Lịch sử link** | 6 link gần nhất kèm ✅/❌ lần dùng cuối; bấm là kết nối lại. Tự kiểm tra lại mỗi 60 giây |

**Vì sao không nhúng thẳng Colab vào app (iframe/WebView)?** Google **chặn đăng nhập
Google trong WebView** (lỗi “disallowed_useragent”), và Colab **không có API** để app bấm
*Run all* hộ. Nên cách khả thi nhất — và đúng chính sách của Google — là Custom Tab +
tự đọc clipboard khi quay lại, đúng như app này đang làm.

Link Colab sinh lúc build trỏ tới **tag/nhánh không chứa dấu `/`** (hoặc commit SHA) vì
Colab không mở được ref bị mã hoá `%2F`. Build từ tag `v*` sẽ tạo link `.../blob/v1.1.0/...`
— ổn định vĩnh viễn; build từ nhánh `arena/...` thì dùng commit SHA của lần build đó.

---

## App có gì

| Màn hình | Nội dung |
|---|---|
| **Tạo ảnh** | Prompt + negative (gập lại), **nhập tiếng Việt có dấu an toàn theo IME**, tự chuyển cụm đã biết sang tag Anh (`tóc dài → long_hair`), gợi ý Anh–Việt ngay khi gõ và chip gợi ý nhanh từ kho offline, thống kê `N tag · M token · mức`, 🧩 **Chuẩn hoá** (thêm tag chất lượng, xếp theo 18 nhóm Illustrious/WAI, khử trùng), ✂️ **Nén** (bỏ tag trùng nghĩa như `eyes` khi đã có `blue_eyes`), chip kích thước + 4 mức phân loại nội dung, tham số nâng cao (seed, steps, CFG, batch, clip skip, hires scale, denoise, hires on/off), nút **Tạo ảnh** + **Huỷ**, tiến trình thật từ `/sdapi/v1/progress` (`⏳ 01:12 · bước 9/25 · 36% · còn ~1m 20s`) |
| **Kho tag** | 95.939 tag được đóng gói trong APK (mọi tag có nghĩa tiếng Việt đều được giữ, kể cả tag hiếm): gõ **tiếng Việt không cần dấu** (`toc dai` → `long_hair`), duyệt đủ 18 nhóm bằng thanh cuộn ngang, chọn nhiều tag rồi **Chèn vào prompt** |
| **Phong cách** | 12 công thức sẵn (màu nước, cel-shading, ukiyo-e, pixel art…) + đủ **506 tag phong cách** lọc theo nhóm/chất liệu, có nghĩa tiếng Việt |
| **Thư viện** | Ảnh tạo xong **tự lưu trên máy** (IndexedDB, không nằm trong RAM): xem ảnh, chia sẻ/tải về, xoá, **dùng lại prompt + seed** |
| **🔌 Máy chủ** | **Mở Colab & chạy** bằng một nút, tự nhận link tunnel khi quay lại app (clipboard), dán link trong clipboard, 6 link gần nhất, copy lệnh `install.sh` để kiểm tra/lấy link mới, **chẩn đoán** 6 endpoint Forge/API ảnh nén, công tắc tự nhận link |
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
node mobile/tests/test_core.mjs          # 37 test logic: prompt, payload, token, tìm/lọc/gợi ý/dịch tag, bắt link Forge
node mobile/tests/test_api.mjs           # 26 test ForgeClient: ảnh nén, chọn endpoint trước job, không nhân đôi job, huỷ
python3 mobile/tests/test_mobile_assets.py   # 20 test dữ liệu/tài nguyên/id HTML/nhập tiếng Việt
python3 mobile/tests/test_mobile_route.py    # 8 test route FastAPI + JPEG + kế thừa API auth
npm i jsdom && node mobile/tests/test_ui_smoke.mjs   # smoke UI thật trên DOM giả + Forge giả
                                                     # (kể cả tab Máy chủ: mở Colab, dán link, tự nhận link, chẩn đoán)
```

`test_core.mjs` chạy payload qua đúng quy ước của `PromptBuilder.payload()`
(`clip_skip → override_settings`, `DPM++ 2M Karras → sampler + scheduler Karras`, bỏ
tham số hires khi tắt hires…) nên sửa một bên mà quên bên kia là test đỏ ngay.

## Cấu trúc thư mục

| File | Việc |
|---|---|
| `app/index.html`, `app/styles.css` | Khung 4 tab + các sheet, CSS mobile (safe-area, nút ≥ 44 px, dark) |
| `app/js/core.js` | Logic thuần: parse tag/trọng số, chuẩn hoá prompt, token, payload, dịch lỗi, `extractForgeUrl` (bắt link tunnel trong log Colab). **Không DOM** → test được bằng Node |
| `app/js/data.js` | Nạp `tags.json(.gz)`, tìm tag Anh↔Việt, 506 phong cách |
| `app/js/api.js` | Gọi Forge: ping, tiến trình, kiểm tra health rồi chọn API nén JPEG/API chuẩn trước khi tạo job, `interrupt` |
| `app/js/store.js` | Cài đặt (localStorage) + ảnh (IndexedDB) |
| `app/js/ui.js` | Nối DOM, 4 tab (thêm **Máy chủ**: Colab, clipboard, chẩn đoán), sheet Cài đặt/Phong cách/Xem ảnh |
| `app/sw.js`, `app/manifest.webmanifest`, `app/icons/` | PWA: cài ra màn hình chính, mở nhanh khi mạng chập chờn |
| `app/data/tags.json(.gz)` | **Sinh ra**, không commit (`.gitignore`) |
| `build_data.py` | Sinh dữ liệu từ `danbooru_e621.csv`, bản dịch, `style_tags.csv`, `prompt_lib` |
| `make_icons.py` | Vẽ icon PNG bằng stdlib (không cần Pillow) |
| `serve.py` | Server thử + proxy Forge + Forge giả (`--mock`) |
| `apk/` | Vỏ Capacitor (`capacitor.config.json`, `package.json`, plugin `@capacitor/browser` cho nút mở Colab) để build APK |
| `tests/` | Test Node (logic), test Python (dữ liệu/tài nguyên), smoke UI (jsdom) |

Dữ liệu tag: mọi tag có `post_count ≥ 200` **hoặc** có bản dịch tiếng Việt →
**95.939 tag**, 4,0 MB JSON / **1,36 MB gz**; app tự dùng `DecompressionStream` để đọc
bản gz, máy cũ không hỗ trợ thì tải bản `.json`. Muốn nhẹ hơn:
`python3 mobile/build_data.py --min-count 500` (66.720 tag, 1,04 MB gz).

## Gỡ lỗi nhanh

| Hiện tượng | Nguyên nhân & cách sửa |
|---|---|
| “Không gọi được máy chủ…” | Link tunnel hết hạn (gradio.live sống ~10 phút–vài giờ) → chạy `bash /content/install.sh --status`, rồi `--only launch,verify --restart` và mở **link mới**. Hoặc app ở origin khác mà Forge thiếu `--cors-allow-origins` |
| Web tạo ảnh bình thường nhưng APK mất kết nối lúc trả ảnh | Web dùng transport Gradio, APK tải JSON base64 lớn. Chạy lại notebook một ô để cập nhật extension + restart Forge; chẩn đoán phải có **Ảnh nén cho điện thoại**. App sẽ gọi `/vi-mobile/api/txt2img` nhận JPEG nhỏ thay vì PNG lớn; không đổi engine/job |
| “Không thấy /sdapi” (404) | Forge chạy thiếu `--api`; bộ cài đã bật sẵn |
| Không ghép dấu tiếng Việt được / Enter làm mất chữ | APK cũ có thể xử lý gợi ý giữa lúc IME ghép dấu. Bản mới chờ `compositionend`, không chặn Enter/keyCode 229 và hỗ trợ chuyển cụm Việt đã biết sang tag Anh |
| Chẩn đoán báo `internal/progress` HTTP 405 | APK cũ gọi nhầm GET; bản mới dùng `POST` với `skip_current_image=true`. Cài lại APK build mới nhất |
| Forge trả 500 / ảnh trắng | Hết VRAM (Hires trên T4): tắt Hires, giảm kích thước, xem `forge.log` |
| Trang `/vi-mobile/` báo thiếu dữ liệu | Chưa sinh dữ liệu: `python3 mobile/build_data.py` (bộ cài chạy tự động ở stage `extras`) |
| Không thấy icon sau khi “Thêm vào MH chính” | Dùng Chrome/Safari (không dùng trình duyệt trong app Facebook/Zalo) |
| Ảnh không lưu vào thư viện | Chế độ ẩn danh chặn IndexedDB — đóng tab ẩn danh, dùng cửa sổ thường |
| Bấm **Mở Colab** ra trang 404 trên Colab | Link dựng từ ref đã bị xoá (nhánh feature) — build lại từ tag `v*`, hoặc Copy lệnh kiểm tra rồi tự mở notebook trong repo |
| Quay lại app mà không tự kết nối | Công tắc **Tự nhận link khi quay lại app** đang tắt, hoặc clipboard không có link (Colab chưa in link) → bấm **Dán link trong clipboard**; Android 12+ chỉ cho đọc clipboard khi bạn vừa thao tác trong app |
| APK không cài được | Bật “Cài ứng dụng không rõ nguồn gốc” cho trình quản lý file; APK debug đã ký sẵn |

## Ghi chú kỹ thuật

- **Ảnh nhẹ cho tunnel**: ưu tiên `POST /vi-mobile/api/txt2img`; extension gọi đúng
  handler txt2img của Forge rồi đổi PNG base64 thành JPEG quality 88. Web/API chuẩn
  không bị sửa và ảnh gốc trong outputs không bị ghi đè. App đọc `/vi-mobile/api/health`
  để chọn endpoint **trước khi tạo job**; sau POST, mọi lỗi mạng/404/5xx đều không gửi
  lại sang endpoint khác.
- **Không có timeout cứng cho việc sinh ảnh**: request txt2img là đồng bộ,
  Forge chỉ trả lời khi xong (Hires trên T4 mất 3–6 phút). App chạy POST và poll
  `/sdapi/v1/progress` song song, nên vẫn thấy tiến trình và huỷ được.
- **Khôi phục dự phòng khi đứt response ảnh**: app đọc `current_image` một lần lúc tiến trình ≥90%.
  Nếu body `txt2img` bị đứt, app chờ/đọc lại preview gần cuối thay vì POST tạo job trùng;
  không có bằng chứng job chạy thì không dùng ảnh cũ.
- **Huỷ** gọi `/sdapi/v1/interrupt` rồi bỏ request — không để Forge chạy tiếp một job
  người dùng đã bỏ.
- API mobile trả JPEG, API chuẩn trả PNG; app lưu **data URL** vào IndexedDB (không nhét vào
  `localStorage` vì giới hạn ~5 MB).
- Payload theo đúng `prompt_lib/builder.py`: `clip_skip` đi qua
  `override_settings.clip_stop_at_last_layers`, sampler `… Karras` tách thành sampler +
  `scheduler=Karras`, tắt Hires thì bỏ luôn 4 khoá `hr_*`/`denoising_strength`.
