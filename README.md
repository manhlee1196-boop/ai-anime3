<div align="center">

<img src="docs/media/logo.png" alt="Mika" width="88" />

# Mika — Bản tiếng Việt

**Trợ lý AI trên điện thoại: giao việc bằng lời, Mika thao tác ứng dụng và web giúp bạn.**

Mika chạy trên một màn hình nền riêng để bạn vẫn dùng điện thoại bình thường.

[English README](README.en.md) · [Tài liệu tiếng Việt](docs/README.vi.md) · [Dự án gốc Mika](https://github.com/wangzan101/Mika)

</div>

> Đây là **bản Việt hóa cộng đồng**, dựa trên [wangzan101/Mika](https://github.com/wangzan101/Mika) tại commit `4387bfeace287fafb73038609efcb00ff6a5f63e` (15-11-2026). Bản này không phải bản phát hành chính thức của tác giả Mika.

## Tình trạng Việt hóa

- Có thể chọn **Tiếng Việt** trong **Cài đặt › Ngôn ngữ và giao diện › Ngôn ngữ**. Trên Android 13 trở lên, ngôn ngữ này cũng xuất hiện trong phần cài đặt ngôn ngữ của riêng ứng dụng.
- Đã dịch đầy đủ các luồng giao diện: trò chuyện, mô hình, điều khiển điện thoại, trình duyệt, lịch và báo cáo tác vụ, cuộc gọi AI, WeChat, MCP, thông báo chủ động, bộ nhớ, cài đặt và quản lý tệp.
- Catalog tiếng Việt hiện bao phủ **100% tài nguyên chuỗi giao diện có thể dịch (3.291/3.291 mục)**; kiểm tra không còn mục nào phải dùng tiếng Anh dự phòng. Bản dịch cộng đồng vẫn cần được người dùng rà soát trong ứng dụng.
- Bạn có thể giao việc và trò chuyện với Mika bằng tiếng Việt; ngôn ngữ trả lời còn tùy vào mô hình AI đã kết nối.
- Tải [APK xem trước tiếng Việt từ GitHub Releases](https://github.com/manhlee1196-boop/ai-anime3/releases/tag/mika-vi-v0.1.43). Đây là bản cài song song (`com.wangzan101.mika.dev`), ký debug, không phải bản chính thức; trình cập nhật trong Mika không cập nhật bản này. Các bản xem trước sau có thể cần gỡ bản cũ trước khi cài nếu chữ ký thay đổi.

## Tính năng chính

| Tính năng | Mô tả |
|---|---|
| Điều khiển ứng dụng | Đọc màn hình, chạm, nhập và cuộn trên màn hình nền ảo; bạn có thể tiếp quản khi cần đăng nhập, xác minh hoặc thanh toán. |
| Trình duyệt tích hợp | Đọc trang web, tìm kiếm, tải tệp và dùng phiên đăng nhập đã lưu trên thiết bị. |
| Trò chuyện và tác vụ | Giao việc bằng ngôn ngữ tự nhiên, tiếp tục trao đổi khi tác vụ đang chạy, hoặc dừng và tiếp tục sau. |
| Lên lịch | Tạo lời nhắc và tác vụ chạy theo giờ, ngày hoặc điều kiện. |
| Tệp và tính toán | Môi trường Linux riêng cho từng cuộc trò chuyện; hỗ trợ xử lý tệp bằng Python, Node và shell trên thiết bị ARM64. |
| Ghi nhớ và kỹ năng | Lưu tùy chọn bạn yêu cầu, xem lại kỹ năng Mika học được và chấp thuận trước khi dùng. |

## Cài đặt và sử dụng

### Yêu cầu

- Android 11 trở lên cho trò chuyện, web và tệp.
- Android 12 trở lên để điều khiển ứng dụng; **Android 14 trở lên được khuyến nghị**.
- Môi trường Linux cần thiết bị ARM64.

### Tạo APK từ mã nguồn

Cần JDK 17 và Android SDK 36. Từ thư mục gốc:

```bash
./gradlew :app:assembleDebug
```

APK thử nghiệm sẽ nằm tại `app/build/outputs/apk/debug/app-debug.apk`.

Sau khi cài, vào **Cài đặt › Mô hình AI** để kết nối nhà cung cấp bằng khóa API hoặc tài khoản được hỗ trợ. Nếu cần Mika thao tác các ứng dụng trên điện thoại, mở **Cài đặt › Điều khiển điện thoại** và làm theo hướng dẫn ghép nối gỡ lỗi không dây; có thể bỏ qua nếu chỉ dùng trò chuyện, web và tệp.

> Ứng dụng giữ cùng mã định danh với dự án gốc. Nếu chữ ký của APK tự biên dịch khác APK đã cài, Android có thể yêu cầu gỡ bản cũ trước khi cài. Hãy sao lưu hoặc xuất dữ liệu quan trọng trước khi gỡ.

## Quyền riêng tư và an toàn

- Mika không có máy chủ riêng. Nội dung bạn gửi và màn hình được chia sẻ chỉ chuyển tới nhà cung cấp mô hình mà bạn tự cấu hình.
- Khóa API và bộ nhớ được mã hóa trên điện thoại; cuộc trò chuyện và lịch sử tác vụ được lưu cục bộ.
- Theo mặc định, Mika chỉ hỏi trước các thao tác có thể tiêu tiền, chẳng hạn đặt hàng hoặc thanh toán. Hãy kiểm tra kết quả của tác vụ quan trọng.
- Tự động thao tác ứng dụng hoặc trang web có thể vi phạm điều khoản của bên thứ ba; hãy tự đánh giá rủi ro trước khi dùng.

## Tài liệu

- [Bắt đầu nhanh và thiết lập tiếng Việt](docs/setup-guide.vi.md)
- [Mục lục tài liệu](docs/README.vi.md)
- [Hướng dẫn mô hình và đăng nhập](docs/models.en.md) (tiếng Anh)
- [Chế độ Hỏi và Tự chủ](docs/modes.en.md) (tiếng Anh)
- [Tuyên bố miễn trừ và quyền riêng tư](docs/disclaimer.en.md) (tiếng Anh)

## Nguồn và giấy phép

Mã nguồn được kế thừa từ [wangzan101/Mika](https://github.com/wangzan101/Mika), giấy phép Apache-2.0. Xem [`LICENSE`](LICENSE), [`NOTICE`](NOTICE) và [`licenses/THIRD_PARTY_NOTICES.md`](licenses/THIRD_PARTY_NOTICES.md). Bản Việt hóa này do cộng đồng thực hiện, không đại diện cho tác giả dự án gốc.
