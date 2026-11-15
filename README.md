# LocalPilot — trợ lý AI Android chạy trên thiết bị

LocalPilot là MVP Android native (Kotlin + Compose) cho trợ lý AI ưu tiên chạy ngoại tuyến. Runtime là **LiteRT-LM** cho Android/Kotlin; model do người dùng tự nhập. Trợ năng chỉ được đọc theo yêu cầu; mỗi hành động UI được xem trước và duyệt riêng. Giọng nói hỗ trợ nhấn-nói và phiên nghe nền có thời hạn do người dùng chủ động bắt đầu, không có nghe luôn/đánh thức nền.

> Repo không lưu APK/model nhị phân. GitHub Actions workflow **Build Android APK** tạo APK debug và lưu artifact 30 ngày; APK chưa được ký phát hành và chưa kèm model.

## Model gợi ý

Có thể thử **Gemma 3 1B IT int4** bản LiteRT-LM từ [litert-community/Gemma3-1B-IT trên Hugging Face](https://huggingface.co/litert-community/Gemma3-1B-IT). Chọn tệp `.litertlm` tương thích Android, ví dụ `gemma3-1b-it-int4.litertlm` (~584 MB). Model có giấy phép/điều kiện Gemma; tải từ nguồn chính thức, xem điều khoản và đủ dung lượng trống trước khi nhập. Dung lượng RAM/tốc độ thực tế phụ thuộc chip và runtime. Không chọn `.task` hoặc GGUF trong app này. **Chưa xác minh chất lượng tiếng Việt của model gợi ý**; prompt yêu cầu trả lời tiếng Việt nhưng năng lực thực tế tùy model được nạp.

Ứng dụng không tải model tự động. Tải model trên Hugging Face bằng trình duyệt/thiết bị khác, rồi chọn tệp trong app. Chưa huấn luyện model riêng: app dùng model instruction-tuned sẵn và yêu cầu nó đề xuất kế hoạch JSON giới hạn cho thao tác UI. Mọi bước được kiểm tra cục bộ trước khi người dùng duyệt.

## Tính năng hiện có

- Inference cục bộ qua LiteRT-LM Kotlin SDK, tệp `.litertlm` được chép vào bộ nhớ riêng của app; app không khai báo quyền `INTERNET`.
- **Giọng nói tiếng Việt:** nút micro nhận dạng một lượt. Nút **Bắt đầu phiên nghe** chủ động bật foreground microphone service có thông báo thường trực; phiên dùng on-device SpeechRecognizer (Android 12+ và thiết bị phải có dịch vụ/ngôn ngữ nhận dạng ngoại tuyến `vi-VN`), tự tắt sau 20 phút và dừng được từ app/thông báo. Không có từ đánh thức, luôn bật, hoặc dự phòng nhận dạng trực tuyến. Khi nhận một câu không phải lệnh dừng, dịch vụ tạm ngưng micro và đưa câu vào thẻ **Lệnh đang chờ**; câu chữ chỉ nằm trong RAM. Người dùng chọn đưa lệnh vào chat rồi nhấn Gửi; không có thao tác nào chạy tự động. Lệnh UI cần snapshot app đích; mỗi kế hoạch chỉ chứa một hành động và cần được xem, duyệt riêng. Sau khi xử lý/bỏ lệnh, người dùng chủ động tiếp tục nghe. Android có thể hạn chế hoạt động nền; nếu không có offline `vi-VN`, tính năng báo không khả dụng, không chuyển sang dịch vụ mạng.
- **Đọc màn hình:** bấm **Chụp app khác** để chờ chụp một lần, chuyển sang app đích, đợi màn hình tải rồi quay lại LocalPilot. Chỉ chụp cây văn bản trợ năng của app đó (tối đa 8.000 ký tự); không đọc giá trị ô nhập hoặc trường mật khẩu. Snapshot một lần chỉ được giữ trong RAM đến khi LocalPilot quay lại nhận, sau đó xóa khỏi buffer; không ghi ra file.
- **Nhập chữ / thao tác UI giới hạn:** mỗi kế hoạch chỉ gồm đúng một hành động `tap` hoặc `type`, trên đúng app đã chụp. Có thể chạm nhãn đang hiện và thay nội dung ô có accessibility hint; text nhập phải có trong yêu cầu của người dùng. LocalPilot hiển thị app đích, nhãn và nội dung trước khi người dùng duyệt hành động đó. Sau xác nhận, LocalPilot đưa về nền; thao tác chạy một lần khi app đích xuất hiện trong 30 giây. Hành động tiếp theo cần yêu cầu, snapshot và phê duyệt mới. Không gửi form/tin nhắn, thanh toán/xóa/chuyển tiền, nhập mật khẩu/OTP/PIN/CVV, shell hoặc gesture tọa độ. Nếu nhãn không khớp hoặc app đổi, thao tác dừng.
- Shizuku tùy chọn qua UserService; chỉ chạy chẩn đoán đọc số lượng app người dùng đã cài. Không nhận lệnh từ model và không thay đổi hệ thống.
- Không đăng nhập, analytics hay lưu hội thoại/prompt vào file. Nội dung chat chỉ nằm trong RAM phiên app.

## Build và chạy

1. Cài Android Studio, JDK 17, Android SDK 35.
2. **Tải APK từ GitHub:** mở tab **Actions**, chọn lần chạy **Build Android APK** thành công, tải artifact `localpilot-debug-apk-<commit>` và giải nén `app-debug.apk`. Workflow cũng chạy tự động mỗi khi có push; có thể chạy thủ công bằng **Run workflow**.
3. Hoặc build cục bộ: mở thư mục repo (`File → Open`) và chờ Gradle Sync tải thư viện, hoặc chạy `./gradlew :app:assembleDebug`; APK đầu ra là `app/build/outputs/apk/debug/app-debug.apk`.
4. Cài APK lên Android API 26+. Chọn model `.litertlm` trong app để nạp; lần đầu nạp có thể mất thời gian.
5. Muốn đọc/điều khiển UI, bật **LocalPilot – đọc nội dung màn hình** trong Cài đặt Trợ năng Android. Android cấp quyền rộng: chỉ bật khi bạn tin tưởng mã nguồn. Quay lại app, nhấn **Chụp app khác**, chuyển sang app đích rồi quay lại LocalPilot để nhận snapshot.
6. Muốn nói một câu, nhấn micro và cấp quyền ghi âm. Muốn nghe trong phiên nền, nhấn **Bắt đầu phiên nghe**, cấp quyền micro (và thông báo nếu muốn thấy thông báo thông thường), rồi chuyển sang app bạn muốn dùng. Khi nhận lệnh, mở LocalPilot từ thông báo, xem thẻ lệnh đang chờ và chọn đưa lệnh vào chat; không có hành động chạy cho đến khi bạn gửi yêu cầu, xem snapshot/kế hoạch và duyệt hành động riêng. Nhận dạng ngoại tuyến cần Android 12+ cùng gói `vi-VN`; nếu không có, tính năng báo không khả dụng và không chuyển sang dịch vụ mạng.
7. Muốn kiểm tra Shizuku, khởi động ứng dụng Shizuku trước, nhấn **Cấp quyền**, chấp thuận rồi chạy kiểm tra. Tính năng này không bắt buộc.

## Giới hạn

- Đọc văn bản accessibility, chưa chụp pixel/OCR; ứng dụng đích có thể không cung cấp nhãn/ô nhập mà LocalPilot cần. Android chỉ cho khởi tạo dịch vụ micro từ giao diện đang hiển thị trong điều kiện cho phép; LocalPilot không tự bật phiên hoặc tự mở màn hình app khác từ nền.
- Đây không phải quyền đồng ý lâu dài: mỗi kế hoạch cần duyệt lại. Đọc kỹ nội dung ô nhập trước khi xác nhận; Android/app đích vẫn có thể có tác dụng phụ ngoài dự kiến.
- Không có macro tự động/lặp nền: chỉ chạy kế hoạch một lần đã duyệt trong 30 giây. Không tự mở/đóng app, không gửi biểu mẫu và không chạy shell tổng quát.
