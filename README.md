# PocketPilot + PocketCanvas — ứng dụng AI trên Android

PocketPilot là ứng dụng Android mẫu cho phép người dùng nhập yêu cầu bằng tiếng Việt, xem trước kế hoạch thao tác rồi xác nhận để điện thoại thực hiện. Bản hiện tại xử lý lệnh bằng bộ phân tích cục bộ theo quy tắc (không gọi mô hình AI hay máy chủ), làm nền tảng an toàn để phát triển thêm.

## Chức năng hiện có

- Giao diện tiếng Việt, nhập yêu cầu và xem trước từng bước trước khi chạy.
- Mở ứng dụng đã cài theo tên (có bí danh cho YouTube, Chrome, Zalo, Facebook, Messenger, Gmail, Maps và Cài đặt).
- Tìm kiếm trong ứng dụng: ví dụ `Mở YouTube và tìm nhạc thư giãn` hoặc `Tìm thời tiết ngày mai`.
- Nhấn nút theo chữ đang hiển thị, nhập vào ô đang được chọn, cuộn lên/xuống, quay lại và về màn hình chính.
- Có thể dừng chuỗi thao tác. Các hành động gửi tin, gửi email, đăng bài, mua hàng, thanh toán và xóa dữ liệu bị chặn trong bản mẫu.

## Mở và cài ứng dụng

1. Mở thư mục repository này trong Android Studio (bản hỗ trợ Android Gradle Plugin 8.6.1).
2. Cài Android SDK Platform 35 nếu Android Studio yêu cầu, rồi chọn **Sync Project with Gradle Files**.
3. Chạy cấu hình `app` lên thiết bị Android thật hoặc emulator (Android 8.0/API 26 trở lên).
4. Trong PocketPilot, nhấn **Thiết lập**. Ở Cài đặt Android, bật dịch vụ Trợ năng **PocketPilot – tự động hóa** và xác nhận cảnh báo của hệ điều hành.
5. Nhập yêu cầu → **Lập kế hoạch** → kiểm tra các bước → **Chạy tác vụ đã xem**.

## Quyền riêng tư và giới hạn

Dịch vụ Trợ năng cần đọc cây giao diện đang hiển thị để tìm nút/ô nhập và thực hiện thao tác. Ứng dụng không khai báo quyền Internet và không gửi nội dung màn hình hay yêu cầu ra ngoài thiết bị. Chỉ bật quyền Trợ năng nếu bạn tin tưởng bản dựng này. Một số ứng dụng không cung cấp nhãn giao diện có thể truy cập được; khi đó thao tác tìm/nhấn/nhập sẽ không hoạt động. Android cũng có thể giới hạn thao tác trên màn hình bảo mật hoặc trong ứng dụng khác.

Đây chưa phải trợ lý hội thoại AI tổng quát: nó chỉ hiểu một nhóm lệnh được hỗ trợ, không tự suy luận chuỗi công việc phức tạp. Các thao tác có ảnh hưởng lớn cần được người dùng hoàn tất trực tiếp. Không nên dùng để tự động hóa hành vi nhạy cảm hoặc trái điều khoản ứng dụng khác.

## PocketCanvas Offline — tạo ảnh AI hoàn toàn trên Android

Repository có module `pocketcanvas`, dùng MediaPipe Image Generator để chạy Stable Diffusion 1.5 trên điện thoại và cung cấp một API tương thích OpenAI cho LocalMind. PocketCanvas giữ model và ảnh ở trên máy; endpoint chỉ lắng nghe tại loopback `127.0.0.1` và được bảo vệ bằng API key ngẫu nhiên. Module cần quyền Android `INTERNET` để mở socket loopback cho LocalMind, nhưng server không bind vào Wi-Fi/LAN và code không gửi prompt/ảnh tới máy chủ bên ngoài.

### Tạo và tải APK trên GitHub Actions

Workflow `.github/workflows/pocketcanvas-apk.yml` tự build APK debug khi có thay đổi liên quan trên nhánh này, hoặc chạy thủ công trong GitHub → **Actions** → **Build PocketCanvas APK** → **Run workflow**. Khi job thành công, mở run đó và tải artifact **PocketCanvas-debug-apk**. APK tải về là bản cài thử (debug), không kèm model weights.

### Cài model và kết nối LocalMind

1. Mở repository trong Android Studio và chọn cấu hình chạy **pocketcanvas** (cấu hình `app` là PocketPilot).
2. Tải gói `sd15-mediapipe.zip` từ [cuesetac/sd15-mediapipe trên Hugging Face](https://huggingface.co/cuesetac/sd15-mediapipe) bằng trình duyệt. Chọn gói MediaPipe, không chọn GGUF/stable-diffusion.cpp.
3. PocketCanvas → **Nhập gói .zip** → chọn ZIP. Model được giải nén vào thư mục riêng tư của app. Cần thêm dung lượng trống để giải nén gói lớn.
4. Nhấn **Bật API cho LocalMind**. Giữ dịch vụ foreground đang chạy (có thông báo) khi chuyển sang LocalMind.
5. Trong LocalMind, thêm server loại **OpenAI-compatible**:
   - Host: `127.0.0.1`; port: `8765`
   - API key: nhấn **Sao chép API key** trong PocketCanvas rồi dán vào LocalMind
   - Mục **Image Model IDs**: `pocketcanvas-sd15`
6. Chọn model ảnh `pocketcanvas-sd15` trong LocalMind. LocalMind gửi prompt tới `POST /v1/images/generations`; PocketCanvas chạy model cục bộ và trả PNG dạng base64. Tắt API bằng nút trong app hoặc thông báo foreground.

Lần tải model đầu tiên cần internet trong trình duyệt; sau khi nhập xong, sinh ảnh hoàn toàn offline. Không có trọng số model được commit vào repository vì kích thước lớn và điều khoản phân phối riêng. Đây là Stable Diffusion 1.5 đã chuyển đổi, **không phải model mới được huấn luyện**. App mặc định 10 bước và cho chỉnh 5–20 để giảm tải, nhưng 4 GB RAM không bảo đảm chạy ổn định trên mọi thiết bị; chipset và bộ nhớ trống cũng ảnh hưởng.

Tham khảo [MediaPipe Image Generator cho Android](https://developers.google.com/mediapipe/solutions/vision/image_generator/android) và [mã nguồn LocalMind](https://github.com/abdulmominsakib/localmind). MediaPipe hỗ trợ prompt và LoRA; PocketCanvas hiện tích hợp text-to-image cơ bản, chưa huấn luyện LoRA.

## Cấu trúc

- `app/` — PocketPilot: trợ lý thao tác điện thoại qua Accessibility Service.
- `pocketcanvas/` — PocketCanvas Offline: text-to-image trên thiết bị bằng MediaPipe.
- `pocketcanvas/src/main/java/vn/pocketcanvas/MainActivity.kt` — giao diện, nhập gói ZIP, suy luận và lưu PNG.
- `app/src/main/java/vn/pocketpilot/TaskPlanner.kt` — phân tích lệnh PocketPilot hoàn toàn trên thiết bị.
- `app/src/main/java/vn/pocketpilot/PhoneAutomationService.kt` — thao tác Android qua Accessibility Service.
