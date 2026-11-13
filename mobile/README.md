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

Bấm **🔌 Máy chủ → Mở Colab (chạy thủ công)** là notebook Colab mở từ app (tab trình duyệt
gắn với app, có nút quay lại); bạn bấm *Runtime → Run all*, rồi chạm **📲 Mở lại Anime3**
trong output Colab. APK mới nhận link Forge và kết nối **không cần copy/dán** (xem
[mục D](#d-chạy-colab-từ-app--quay-lại-app-không-cần-dán-link)).

> Phương án này chỉ dùng Colab và không có thủ thuật giả hoạt động để ngăn Colab tự ngắt.
> Cách deep link, đường fallback PWA/APK cũ và luồng khôi phục được mô tả trong
> [phương án Colab-only](RUN_IN_APP_PLAN.md).

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

Cài xong: mở app → tab **🔌 Máy chủ** → **Mở Colab (chạy thủ công)** → *Runtime → Run all*
→ chạm **📲 Mở lại Anime3** trong output Colab. APK nhận tunnel và kết nối ngay, không cần
copy/dán. APK cũ vẫn có thể dán link Forge vào ô địa chỉ → **Kết nối**.

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
4. Mở app → tab **🔌 Máy chủ** → **Mở Colab (chạy thủ công)**, bấm *Runtime → Run all*
   trong Colab rồi chạm **📲 Mở lại Anime3**. Nếu dùng APK cũ/PWA, dán link tunnel (ví dụ
   `https://abc123.gradio.live`) rồi **Kết nối**.

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

## D. Chạy Colab từ app → quay lại app không cần dán link

Mục tiêu: dùng **Colab-only** nhưng không bắt người dùng chép URL tunnel. App không nhúng
Colab (xem lý do bên dưới), mà mở notebook ở **Custom Tab** — vẫn nằm trong app, có nút quay
lại. Bước cấp GPU và *Runtime → Run all* luôn do bạn xác nhận trong Colab.

| Bước / nút | Việc nó làm |
|---|---|
| **🚀 Mở Colab (chạy thủ công)** | Mở đúng notebook `colab/WAI_v17_1click.ipynb` của repo trên Colab (Custom Tab trong APK, tab mới trên web). Bạn chọn GPU và bấm *Runtime → Run all* |
| **📲 Mở lại Anime3** ⭐ | Sau khi Forge tạo link, notebook hiện nút này. Chạm nút → `anime3://connect?...` mở APK → app nhận URL `gradio.live`/`trycloudflare.com`, ping Forge và kết nối **không cần clipboard** |
| **🌐 Forge trong app** | Khi đã kết nối, mở giao diện Forge thật trong một sheet iframe của app: có tải lại và nút ↗ chuyển sang Chrome Custom Tab nếu tunnel chặn iframe. Chỉ nhúng Forge, **không nhúng Colab/Google login** |
| *(fallback)* **Tự nhận / Dán clipboard** | PWA hoặc APK cũ không có deep link vẫn đọc `*.gradio.live` / `*.trycloudflare.com` từ clipboard khi quay lại, hoặc dùng nút **📋 Dán link Forge** |
| **📄 Copy lệnh kiểm tra** | Copy `bash /content/install.sh --status` để dán vào Colab khi không thấy link |
| **♻️ Copy lệnh lấy link mới** | Copy `bash /content/install.sh --only launch,verify --restart` — link hết hạn thì chạy lệnh này; copy URL mới để app nhận clipboard. Muốn dùng deep link lại, chạy lại ô notebook một lần rồi chạm **📲 Mở lại Anime3** |
| **🩺 Chẩn đoán kết nối** | Gọi song song 6 endpoint (`options`, `cmd-flags`, `sd-models`, `progress`, `internal/progress`, `vi-mobile/api/health`) bằng đúng GET/POST; kiểm tra **job nền + file stream** |
| **Theo dõi phiên & tự kết nối lại** | Khi app đang mở, ping lại mỗi 60 giây nếu kết nối khoẻ; nếu **cùng link** lỗi, app tự thử lại theo backoff 30 giây đến tối đa 4 phút và thử ngay khi mạng trở lại. App đi background/offline thì dừng, nên đây không phải keep-alive Colab; URL tunnel mới vẫn cần nút **📲 Mở lại Anime3** |

Deep link native chỉ chấp nhận URL HTTPS `*.gradio.live`/`*.trycloudflare.com`, được lưu
một lần rồi xoá sau khi app đọc. App không giữ Google credential, không auto-click và không
có cách hợp lệ để bảo đảm Colab không tự ngắt. Xem luồng và giới hạn đầy đủ trong
[phương án Colab-only](RUN_IN_APP_PLAN.md).

**Vì sao không nhúng thẳng Colab vào app (iframe/WebView)?** Google **chặn đăng nhập
Google trong WebView** (lỗi “disallowed_useragent”), và Colab **không có API** để app bấm
*Run all* hộ hay bảo đảm runtime không bị ngắt. Vì vậy Custom Tab + nút deep link do người
dùng chạm là đường trực tiếp nhất mà vẫn minh bạch.

Link Colab sinh lúc build trỏ tới **tag/nhánh không chứa dấu `/`** (hoặc commit SHA) vì
Colab không mở được ref bị mã hoá `%2F`. Build từ tag `v*` sẽ tạo link `.../blob/v1.1.0/...`
— ổn định vĩnh viễn; build từ nhánh `arena/...` thì dùng commit SHA của lần build đó.

---

## S3 / Cloudflare R2 (tuỳ chọn, khuyến nghị cho APK)

Không cấu hình object storage thì app vẫn tải file local từ Forge bằng HTTP Range. Khi có
S3/R2, worker upload **file ảnh gốc** và manifest chỉ trả **signed URL**; credential không
đi qua APK. Thêm các giá trị sau vào **Colab Secrets**, bật **Notebook access**, rồi chạy
lại notebook một ô để cài `boto3` và restart Forge:

| Secret | Bắt buộc | Ý nghĩa |
|---|---|---|
| `ANIME3_S3_BUCKET` | ✅ | Tên bucket |
| `ANIME3_S3_ENDPOINT_URL` | R2/S3 tương thích | R2: `https://<account_id>.r2.cloudflarestorage.com`; AWS S3 có thể để trống |
| `ANIME3_S3_ACCESS_KEY_ID` | ✅ | Access key của token chỉ có quyền cần thiết trên bucket |
| `ANIME3_S3_SECRET_ACCESS_KEY` | ✅ | Secret key; không dán vào code/notebook/APK |
| `ANIME3_S3_REGION` | — | Mặc định `auto`; AWS có thể đặt region thật |
| `ANIME3_S3_PREFIX` | — | Thư mục object, mặc định `anime3` |
| `ANIME3_S3_SIGNED_TTL` | — | Thời hạn signed URL 300–86400 giây, mặc định 3600 |

Bucket nên **private**, có lifecycle tự xoá object tạm sau vài ngày. CORS của bucket cần
cho `GET`/`HEAD` từ `https://localhost` (APK) và origin tunnel khi dùng PWA; cho header
`Range`, expose `Content-Length`, `Content-Range`, `Accept-Ranges`, `ETag`. Nếu upload hoặc
cấu hình S3 lỗi, cùng job vẫn hoàn tất bằng file local và manifest có `storage_warning`;
app **không tạo lại ảnh**.

## App có gì

| Màn hình | Nội dung |
|---|---|
| **Tạo ảnh** | Hai chế độ gọn **Từ mô tả / Từ ảnh**. Img2img chọn PNG/JPEG/WebP từ máy hoặc Thư viện, xem trước ảnh init, denoise 0,05–1, ba chế độ resize; Hires chỉ hiện ở txt2img. Prompt + negative (gập lại), **nhập tiếng Việt có dấu an toàn theo IME**, tự chuyển cụm đã biết sang tag Anh (`tóc dài → long_hair`), gợi ý Anh–Việt ngay khi gõ và chip gợi ý nhanh từ kho offline, thống kê `N tag · M token · mức`, 🧩 **Chuẩn hoá** (thêm tag chất lượng, xếp theo 18 nhóm Illustrious/WAI, khử trùng), ✂️ **Nén** (bỏ tag trùng nghĩa như `eyes` khi đã có `blue_eyes`), chip kích thước + 4 mức phân loại nội dung, tham số nâng cao (seed, steps, CFG, batch, clip skip, **Hires scale/steps/upscaler/denoise**, hires on/off), nút **Tạo ảnh** + **Huỷ**, tiến trình thật từ `/sdapi/v1/progress` (`⏳ 01:12 · bước 9/25 · 36% · còn ~1m 20s`) |
| **Kho tag** | 95.939 tag được đóng gói trong APK (mọi tag có nghĩa tiếng Việt đều được giữ, kể cả tag hiếm): gõ **tiếng Việt không cần dấu** (`toc dai` → `long_hair`), duyệt đủ 18 nhóm bằng thanh cuộn ngang, chọn nhiều tag rồi **Chèn vào prompt** |
| **Phong cách** | 12 công thức sẵn (màu nước, cel-shading, ukiyo-e, pixel art…) + đủ **506 tag phong cách** lọc theo nhóm/chất liệu, có nghĩa tiếng Việt |
| **Thư viện** | Ảnh tạo xong **tự lưu trên máy** (IndexedDB, không nằm trong RAM): xem ảnh, chia sẻ/tải về, xoá, **dùng lại prompt + seed**, **Biến đổi bằng img2img**, **Upscale ảnh đã có** 1.5–4× bằng RealESRGAN Anime/Lanczos/Nearest; bản mới lưu riêng, giữ ảnh gốc; chặn ảnh vào >20 MiB hoặc cạnh ra >4096 px |
| **🔌 Máy chủ** | Mở notebook Colab (**bạn chạy Run all thủ công**) rồi chạm **📲 Mở lại Anime3** để APK nhận tunnel không cần dán link; mở **🌐 Forge trong app** bằng iframe sau khi kết nối (↗ Custom Tab nếu bị chặn); clipboard là fallback cho PWA/APK cũ; có lịch sử link, lệnh `install.sh`, chẩn đoán 6 endpoint Forge + job API, theo dõi foreground có backoff |
| **Cài đặt** | Địa chỉ Forge, tài khoản API (`--api-auth`), tag chất lượng/negative/sampler mặc định, công thức phong cách, cài PWA, xoá thư viện |

Preset chất lượng/sampler vẫn lấy từ `prompt_lib/system_tags.py` (steps 25, CFG 6,
Euler a, clip skip 2). Riêng cấu hình mobile an toàn hơn cho T4: **832×1216, batch 1,
Hires tắt mặc định**. Khi tự bật Hires: 1.5×, 12 steps, denoise 0.35, RealESRGAN Anime 6B.
Bạn vẫn chỉnh tay; app chặn scale ngoài 1.1–2, Hires steps ngoài 1–60, denoise
ngoài 0.1–0.75, kích thước không chia hết cho 8 và cảnh báo đầu ra trên 2,5 MP. Cấu hình
đã lưu trên máy không bị reset khi cập nhật APK.

**Dùng img2img:** chọn **Từ ảnh → Chọn ảnh từ máy**, hoặc mở ảnh trong Thư viện rồi bấm
**Biến đổi bằng img2img**. Denoise thấp giữ nhiều nét gốc; 0,55 là mặc định, trên 0,8 app
cảnh báo ảnh có thể thay gần như toàn bộ. Kích thước đầu ra vẫn do chip Độ phân giải quyết
định. App gửi đúng một `init_images`, không gửi Hires và không trả ảnh init trong kết quả.

## Chạy thử ở máy tính (không cần GPU)

```bash
python3 mobile/build_data.py         # một lần, ~12 giây
python3 mobile/serve.py --mock       # http://127.0.0.1:8787 — Forge giả, có tiến trình + ảnh
python3 mobile/serve.py              # hoặc trỏ Forge thật (mặc định 127.0.0.1:7860)
python3 mobile/serve.py --forge https://abc123.gradio.live --port 8787
```

`serve.py` chuyển tiếp `/sdapi/*` sang Forge, nên mở từ **điện thoại cùng Wi-Fi** bằng
`http://<IP-máy-tính>:8787` là dùng được (địa chỉ IP được in ra khi khởi động). Chế độ
`--mock` dựng Forge giả: tạo `job_id`, tiến trình tăng dần, **Huỷ** hoạt động, manifest và
file PNG gradient có HTTP Range — đủ kiểm toàn bộ giao diện mà không tốn giây GPU nào.

## Kiểm thử

```bash
node mobile/tests/test_core.mjs          # 40 test logic: prompt, payload txt2img/img2img/Hires, token, tra tag, link Forge
node mobile/tests/test_api.mjs           # 21 test ForgeClient: txt2img/img2img/extras job, manifest, Blob, retry, Range, huỷ
python3 mobile/tests/test_mobile_assets.py   # 23 test dữ liệu/tài nguyên/id HTML/nhập tiếng Việt
python3 mobile/tests/test_mobile_route.py    # 12 test job FastAPI/img2img/Extras, PNG gốc, S3, Range, idempotency, auth
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
| `app/js/api.js` | Health, `POST /jobs`, poll trạng thái, manifest, tải Blob signed/local có tiến trình + resume Range, `DELETE /jobs/{id}`; không fallback base64 |
| `app/js/store.js` | Cài đặt (localStorage) + Blob ảnh và thumbnail nhỏ (IndexedDB) |
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
| Web tạo ảnh nhưng APK mất kết nối lúc trả ảnh | Cập nhật notebook/extension để có **Job nền & file stream**. App chỉ nhận JSON nhỏ rồi tải file gốc từ S3/R2 hoặc local Range; lỗi download được retry mà không tạo job mới |
| Chẩn đoán thiếu `async_jobs` | Extension Colab đang ở bản cũ. Chạy lại notebook một ô và dùng link mới; app cố ý không quay lại `/vi-mobile/api/txt2img` base64 |
| Signed URL tải bị CORS | Bucket chưa cho `GET`/`HEAD` từ `https://localhost` (APK) hoặc origin PWA; kiểm tra lại CORS theo mục S3/R2 |
| Manifest có `storage_warning` | Upload S3/R2 lỗi; ảnh vẫn ở cùng job và app tải file local. Kiểm tra credential, endpoint, quyền bucket rồi dùng job sau |
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

- **Job bất đồng bộ**: `POST /vi-mobile/api/jobs` validate payload rồi trả `202 {job_id}`.
  Một worker gọi đúng handler txt2img, img2img hoặc `extra-single-image` theo `operation`;
  app poll `GET /jobs/{id}` và đọc tiến trình chuẩn song song. `/health` có
  `img2img_available`, `extras_available` và `active_jobs` để chặn restart khi bận. Request tạo job không bị giữ trong suốt thời gian GPU chạy.
- **Idempotency**: client gửi một khoá ngẫu nhiên cho mỗi lần bấm; server lưu hash của
  operation + khoá cùng `job.json`, nên cùng khoá ở img2img/txt2img không trả nhầm ảnh.
  Trùng khoá trong cùng operation trả lại job cũ. Lỗi đọc trạng thái chỉ retry `GET`, không POST lại.
- **Manifest + file gốc**: khi xong, `GET /jobs/{id}/result` chỉ chứa metadata, MIME, kích
  thước và URL file. Worker giữ PNG/JPEG/WebP gốc, không đưa base64 vào response và không
  nén lại thành JPEG. S3/R2 trả signed URL; local fallback stream binary có một Range `bytes`.
- **Retry download**: app tải Blob, hiện tiến trình từng file và thử tối đa ba lượt. Nếu đã có
  một phần file thì gửi `Range: bytes=<đã có>-`; nếu server bỏ qua Range thì đọc lại từ đầu,
  không nối trùng byte. Không dùng `current_image` recovery.
- **Huỷ/restart**: `DELETE /jobs/{id}` bỏ queued job hoặc gọi interrupt cho running job. Job
  queued/running/uploading khi Forge restart được đánh dấu lỗi gián đoạn, không tự chạy lại.
- **Bộ nhớ**: app lưu Blob trong IndexedDB, hiển thị/chia sẻ bằng Object URL và thu hồi URL;
  chỉ thumbnail JPEG nhỏ dùng data URL. Credential S3 chỉ ở environment của Colab/Forge.
- Route job/file kế thừa dependencies auth của `/sdapi/v1/txt2img`; signed URL không nhận
  Basic Auth của Forge. Web/API chuẩn và ảnh trong outputs không bị thay đổi.
- Payload theo đúng `prompt_lib/builder.py`: `clip_skip` đi qua
  `override_settings.clip_stop_at_last_layers`, sampler `… Karras` tách thành sampler +
  `scheduler=Karras`, tắt Hires thì bỏ luôn 4 khoá `hr_*`/`denoising_strength`.
