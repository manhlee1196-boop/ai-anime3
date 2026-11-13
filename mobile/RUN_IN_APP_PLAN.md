# Phương án Colab-only: chạy từ app và quay lại app không cần dán link

## Mục tiêu và giới hạn

Phương án này **chỉ dùng Google Colab** làm GPU runtime. Không cần Google Drive, VPS GPU,
Firebase hay một backend trung gian khác.

“Chạy trực tiếp trên app” ở đây có nghĩa là người dùng bắt đầu từ Anime3 APK, tạo runtime
Colab, trở về APK và tạo ảnh trong APK mà không phải chép URL tunnel. **Không có nghĩa model
WAI v17 chạy trong điện thoại**: checkpoint SDXL khoảng 6,5 GB và suy luận cần GPU Colab.

Google yêu cầu người dùng đăng nhập/chọn GPU trong trình duyệt và Colab không cung cấp API
để APK bấm `Runtime → Run all` thay người dùng. Vì vậy bước xác nhận đó vẫn thủ công. App
không dùng auto-click, giả hoạt động, ping nền hay cách né timeout của Colab.

## Luồng Colab-only được triển khai

```text
Anime3 APK
  │  1. Mở notebook bằng Chrome Custom Tab
  ▼
Google Colab (người dùng chọn GPU, Run all)
  │  2. Forge + Gradio share / Cloudflare quick tunnel tạo URL HTTPS
  │  3. Notebook hiện nút deep link anime3://connect?url=<URL đã mã hoá>
  ▼
Anime3 APK
  │  4. Nhận URL, kiểm tra Forge API và tự kết nối
  ▼
Tạo job / xem tiến trình / tải ảnh trong app
```

### Trải nghiệm sử dụng

1. Mở **Anime3 → Máy chủ → Mở Colab (chạy thủ công)**.
2. Đăng nhập Google nếu cần, chọn GPU và bấm **Runtime → Run all** trong notebook một ô.
3. Khi cài xong, Colab hiện nút **📲 Mở lại Anime3**.
4. Chạm nút này. Android mở đúng APK qua `anime3://connect?...`; app nhận URL tunnel,
   gọi health/API và chuyển sang trạng thái đã kết nối.
5. Tạo ảnh hoàn toàn trong app. Không cần copy/dán link trong đường chính.

Deep link chỉ nhận URL HTTPS của `*.gradio.live` hoặc `*.trycloudflare.com` — hai tunnel
mà notebook hỗ trợ. URL từ custom scheme là dữ liệu không tin cậy, nên app/native plugin
từ chối các host/scheme khác.

### Khả năng tương thích

| Client | Cách quay lại app |
|---|---|
| APK mới build từ nhánh này | Nút **📲 Mở lại Anime3**; không cần clipboard |
| APK cũ | Copy URL tunnel trong output Colab, quay lại app để tự nhận clipboard hoặc bấm **Dán link Forge** |
| PWA/trình duyệt | Notebook hiện link `<tunnel>/vi-mobile/`; mở link này để chạy giao diện web cùng Forge |

## Thành phần kỹ thuật

### APK Android

- `AndroidManifest` đăng ký custom scheme `anime3://connect` và dùng `singleTask` để deep
  link quay vào WebView đang mở thay vì tạo thêm một instance app.
- `Anime3ColabPlugin` lưu callback hợp lệ tạm thời trong `SharedPreferences`; vì Custom Tab
  có thể trả app trước khi WebView sẵn sàng, JavaScript lấy callback theo kiểu consume-once.
- `ui.js` xác minh lại URL, lưu lịch sử link, ping Forge rồi kết nối. Nếu deep link không có
  (PWA/APK cũ), đường clipboard hiện có vẫn là fallback.

### Notebook Colab một ô

- Trong khi in log cài đặt, notebook chỉ nhận dòng `Link public: https://...`.
- Sau khi installer thành công, notebook percent-encode URL và hiện một nút HTML rõ ràng
  **📲 Mở lại Anime3**. Người dùng chủ động chạm nút; notebook không tự điều hướng hoặc
  chạy JavaScript giả thao tác.
- Tùy chọn `share`/`cloudflared` vẫn được người dùng chọn trong form notebook. Cả hai đều
  được deep link hỗ trợ.

## Khôi phục khi Colab/tunnel ngắt

Không có cơ chế hợp lệ nào bảo đảm runtime Colab không bị thu hồi hoặc tunnel không hết hạn.
Thay vì hứa “chống ngắt 100%”, app thực hiện phục hồi rõ ràng:

1. Chỉ khi app đang foreground, app kiểm tra Forge mỗi 60 giây khi kết nối khỏe.
2. Nếu lỗi, app thử lại theo backoff: 30 giây → 60 giây → 120 giây → tối đa 4 phút.
   App background/offline không ping.
3. Khi link chết, mở lại Colab từ tab **Máy chủ**:
   - runtime còn sống: chạy `bash /content/install.sh --only launch,verify --restart`;
   - runtime đã dừng: kết nối runtime/GPU rồi **Run all**.
4. Khi có tunnel mới, chạm **📲 Mở lại Anime3** lần nữa. App thay URL cũ, không đánh dấu
   URL mới “sống” bằng phản hồi chậm từ URL cũ.
5. Prompt/cài đặt/thư viện ảnh local vẫn ở app. Ảnh chỉ nằm `/content` sẽ mất nếu runtime
   bị xóa, vì vậy tải ảnh cần giữ về máy trước.

## Tiêu chí nghiệm thu

- Người dùng không phải dán URL khi dùng APK mới: Run all → chạm **Mở lại Anime3** → app kết nối.
- Callback không mở thêm Activity/WebView và không nhận host lạ.
- Mất mạng/tunnel không tạo lại job ảnh tự động; app chỉ retry đọc trạng thái.
- App không có loop fake activity, auto-click Colab, background keep-alive hoặc credential Google.
- PWA và APK cũ vẫn hoạt động qua đường clipboard/link web dự phòng.
