# Phương án vận hành “trong app” và xử lý mất phiên Colab

## Quyết định ngắn

- **Không thể chạy WAI-Illustrious v17 hoàn toàn trên điện thoại.** Model SDXL khoảng 6,5 GB và luồng suy luận cần GPU VRAM khoảng 16 GB; APK/PWA là client, không phải nơi chạy model.
- **Có thể để toàn bộ trải nghiệm của người dùng ở trong app.** App lưu prompt, tạo job, xem tiến trình, nhận ảnh, lưu/chia sẻ và phục hồi kết nối; việc suy luận chạy trên một GPU backend.
- **Google Colab chỉ nên là lựa chọn thử nghiệm hoặc dự phòng.** Không có API được hỗ trợ để app tự bấm *Run all*, không thể đăng nhập Google trong WebView, và app không thể giữ một runtime Colab không bị nhà cung cấp ngắt.
- **Không triển khai thủ thuật giả hoạt động/auto-click/keep-alive để né giới hạn Colab.** Chúng không đáng tin cậy, có thể vi phạm điều khoản của nhà cung cấp và vẫn không cứu được runtime khi bị thu hồi. Thay vào đó, app chỉ giám sát khi ở foreground và dẫn người dùng khôi phục một phiên hợp lệ.

## 1. Phân biệt ba nghĩa của “chạy toàn bộ trong app”

| Mục tiêu | Có khả thi? | Phương án |
|---|---|---|
| Mọi thao tác của người dùng ở trong APK/PWA | Có | App là giao diện duy nhất; backend trả job/ảnh qua API.
| Model WAI v17 chạy ngay trên điện thoại | Không với cấu hình hiện tại | Cần thay sang model nhỏ, chất lượng/tốc độ khác hẳn; không dùng WAI v17.
| App tự khởi động/giữ mãi Google Colab | Không nên và không được bảo đảm | Người dùng mở Colab trong Chrome Custom Tab, cấp GPU và chạy notebook; app lo phát hiện/phục hồi link.

Vì vậy, kiến trúc nên tách **trải nghiệm trong app** khỏi **nơi có GPU**. Người dùng không phải mở giao diện Forge; họ chỉ dùng app. Nhưng backend GPU vẫn cần tồn tại ở Colab, PC có GPU, hoặc máy chủ GPU riêng.

## 2. Phương án A — Colab tích hợp trong app (dùng ngay, chi phí thấp)

Đây là chế độ có sẵn của repo và phù hợp để thử model hoặc dùng không liên tục.

```text
APK/PWA Anime3
  ├─ Chrome Custom Tab → notebook Colab
  │       └─ người dùng đăng nhập, chọn GPU, Runtime → Run all
  ├─ app nhận link tunnel từ clipboard khi quay lại
  └─ HTTPS → Forge + mobile job API trong runtime Colab
                      └─ PNG/JPEG/WebP → app / S3-R2 tùy chọn
```

### Luồng vận hành

1. Trong tab **Máy chủ**, bấm **Mở Colab (chạy thủ công)**.
2. Colab mở trong Chrome Custom Tab (APK) hoặc tab mới (PWA). Người dùng chọn GPU và bấm **Runtime → Run all**.
3. Notebook in link public. Người dùng copy link, quay lại app; app nhận link từ clipboard, ping Forge, ghi lịch sử link và kết nối.
4. App tạo job bất đồng bộ, poll trạng thái và tải ảnh binary. App không gửi lại POST tạo ảnh chỉ vì một lần đọc trạng thái mất mạng.
5. Khi tunnel/link chết, app báo lỗi, giữ cấu hình/prompt/ảnh local, mở lại notebook để người dùng kết nối runtime rồi nhận link mới.

### Cơ chế chống *mất việc*, không phải né ngắt runtime

Các hành vi nên có trong app:

- **Theo dõi foreground:** chỉ ping health/API khi app đang hiện trên màn hình. Khi app đi background, dừng lịch kiểm tra; đây là monitor kết nối chứ không phải tín hiệu giả để giữ Colab sống.
- **Phát hiện link chết nhanh:** hiển thị trạng thái kết nối, lưu sáu link gần nhất, kiểm tra API/model/progress/job API bằng nút chẩn đoán.
- **Khôi phục một chạm có người xác nhận:** mở lại notebook, copy lệnh `--status` hoặc lệnh tạo link mới; sau khi người dùng chạy lệnh/Run all, app tự nhận URL mới từ clipboard.
- **Không mất dữ liệu trên máy:** cài đặt, prompt đang dùng và thư viện ảnh thuộc app; kết quả cần giữ lâu nên bật S3/R2 hoặc tải về máy. Runtime Colab bị xoá sẽ mất dữ liệu trong `/content`.
- **Không trùng job:** giữ idempotency key trên đường tạo job; nếu đường truyền rớt trong lúc poll, chỉ thử lại GET trạng thái, không âm thầm tạo ảnh lần nữa.

### Giới hạn cần chấp nhận

- Colab có thể thu hồi GPU/runtime hoặc tunnel có thể hết hạn. Không có JavaScript, service worker, notification hay app Android nào có thể bảo đảm ngăn việc đó.
- Chrome Custom Tab là bắt buộc cho đăng nhập Google; nhúng Colab vào WebView dễ bị chặn `disallowed_useragent`.
- Việc bấm **Run all** phải do người dùng thực hiện. Không lưu tài khoản Google, cookie Colab hay script auto-click vào app.

Phương án A giúp thao tác gần như ở trong app, nhưng **không phù hợp cho dịch vụ luôn sẵn sàng**.

## 3. Phương án B — App duy nhất + GPU backend bền vững (khuyến nghị)

Nếu mục tiêu là mở app lúc nào cũng tạo được ảnh, thay Colab bằng GPU do mình quản lý. Với người dùng cuối, mọi thứ vẫn diễn ra trong app; chỉ hạ tầng suy luận ở phía server.

```text
Anime3 APK/PWA
  │ HTTPS + token theo thiết bị
  ▼
api.anime3.example (DNS ổn định, reverse proxy, TLS, rate limit)
  ├─ Mobile Job API (queue, idempotency, trạng thái, manifest)
  ├─ Forge worker GPU / ComfyUI worker GPU
  │     └─ persistent volume: model, LoRA, output tạm
  ├─ object storage private (S3/R2) → signed URL cho ảnh
  └─ monitoring: health, GPU/VRAM, disk, queue, restart alert
```

### Thành phần bắt buộc

1. **Máy có GPU bền vững:** VM GPU, máy chủ GPU thuê theo giờ, hoặc PC cá nhân có GPU chạy liên tục. Dùng persistent volume để không tải lại checkpoint sau mỗi lần khởi động.
2. **Worker quản lý tiến trình:** Docker Compose hoặc systemd chạy Forge và mobile API, có healthcheck/restart policy. Chỉ restart khi hàng đợi rỗng hoặc theo thao tác quản trị rõ ràng.
3. **URL ổn định:** domain riêng + HTTPS reverse proxy. Không dùng URL tunnel ngẫu nhiên làm địa chỉ chính. Nếu dùng tunnel, tunnel phải thuộc hạ tầng của mình và có hostname cố định.
4. **Bảo mật:** xác thực token theo thiết bị/người dùng, HTTPS, CORS chỉ cho origin cần thiết, rate limit. Không để Forge API công khai không mật khẩu; không nhúng secret S3/R2 vào APK.
5. **Ảnh và dữ liệu:** object storage private + signed URL ngắn hạn, lifecycle xoá ảnh tạm, ảnh người dùng tải/lưu trong app. Sao lưu metadata/job nếu cần lịch sử dài hạn.
6. **Quan sát vận hành:** health endpoint, log tập trung, cảnh báo khi worker/GPU/tunnel chết và số liệu hàng đợi. Điều này mới là cách phát hiện sự cố khi app đang đóng.

### Những thay đổi app cần làm cho phương án B

- Màn hình đăng nhập/ghép thiết bị và lưu **access token an toàn**, thay vì Basic Auth cố định.
- Danh sách backend: `Production`, `Máy nhà`, `Colab dự phòng`; Production là mặc định, Colab không còn là đường chính.
- `SessionSupervisor` ở client: kiểm tra khi foreground, retry có backoff, hiển thị thời điểm kiểm tra gần nhất; không giữ socket/ping ở background để đánh lừa nhà cung cấp.
- Lưu `job_id`, request fingerprint và trạng thái tối thiểu trong IndexedDB để mở app lại có thể hỏi server về job chưa xong.
- Nhận thông báo hoàn tất qua push notification từ backend (tùy chọn). Push chỉ thông báo kết quả; không có tác dụng giữ GPU/runtime tồn tại.

## 4. Lộ trình đề xuất

### P0 — an toàn và rõ ràng (ngay trong app)

- Giữ Custom Tab + tự nhận clipboard + lịch sử link + chẩn đoán đang có.
- Đổi nhãn/hướng dẫn để nói rõ **mở Colab và chạy thủ công**, tránh hứa app tự chạy notebook.
- Chỉ monitor khi app foreground; khi lỗi, retry theo backoff để giảm request vô ích tới tunnel chết.
- Hiển thị hướng khôi phục: link hết hạn → mở Colab → user chạy lại notebook/lệnh → copy link → app tự kết nối.

**Tiêu chí đạt:** app không tạo trùng ảnh khi mạng rớt, không mất ảnh đã lưu local, không chạy ping nền/keep-alive giả và người dùng biết rõ bước cần làm khi Colab chết.

### P1 — chuyển backend ổn định

- Đóng gói Forge + extension mobile job API thành một deployment lặp lại được.
- Tạo domain/TLS/auth, persistent volume và S3/R2.
- Chạy smoke test generate/reconnect sau deploy; đặt health alert.
- Thêm server Production vào app rồi cho Colab thành fallback.

**Tiêu chí đạt:** app mở lại sau nhiều giờ/ngày vẫn gọi được cùng URL; restart worker không làm mất ảnh đã upload; app hiển thị được lỗi backend có thể hành động.

### P2 — trải nghiệm production

- Hàng đợi nhiều người dùng, quota/rate limit, tài khoản, analytics không chứa prompt nhạy cảm.
- Push khi job hoàn thành, dashboard admin và chính sách xoá ảnh.
- Tự động rolling restart chỉ khi không có job hoặc drain queue xong.

## 5. Phương án không chọn

| Không chọn | Lý do |
|---|---|
| JavaScript click/chuột giả, vòng lặp giữ tab Colab hoạt động | Né cơ chế idle, dễ hỏng và không bảo đảm runtime/GPU.
| Service worker ping Colab khi app đóng | Service worker không đáng tin cậy cho tác vụ dài; cũng không giải quyết việc Colab thu hồi runtime.
| Nhúng Colab vào WebView | Đăng nhập Google có thể bị chặn; không có API an toàn để bấm Run all.
| Nhét checkpoint WAI v17 vào APK | Kích thước, VRAM, nhiệt độ và pin không đáp ứng; cập nhật model cũng không khả thi.
| Lưu cookie/mật khẩu Google hoặc secret object storage trong app | Rủi ro lộ tài khoản/credential nghiêm trọng.

## Khuyến nghị cuối

- Nếu cần thử nghiệm/cá nhân: dùng **Phương án A**, chấp nhận reconnect có người dùng xác nhận.
- Nếu cần “mở app là dùng được”, ít gián đoạn: đầu tư **Phương án B**. Đây là con đường duy nhất để có tính sẵn sàng thực tế mà không phụ thuộc vào việc giữ Colab sống bằng mẹo.
- Không nên hứa hoặc xây tính năng “chống ngắt Colab 100%”; hãy hứa và kiểm thử **phát hiện nhanh, không mất dữ liệu, khôi phục rõ ràng**.
