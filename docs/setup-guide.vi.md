# Thiết lập điều khiển điện thoại

Hướng dẫn này giúp bạn ghép nối điện thoại với Mika. Thao tác thường mất khoảng 3–5 phút và chỉ cần làm một lần.

## Trước khi bắt đầu

- Cần Android 12 trở lên để Mika thao tác ứng dụng; Android 14 trở lên được khuyến nghị. Mika vẫn cài được trên Android 11 nhưng chỉ dùng trò chuyện, web và tệp.
- Điện thoại cần kết nối với Wi-Fi để ghép nối. **Không cần internet**; chỉ cần cùng mạng không dây.
- Không cần máy tính nếu điện thoại hỗ trợ Gỡ lỗi không dây.
- Có thể bỏ qua thiết lập này nếu chỉ dùng trò chuyện, trình duyệt và tệp.

Tên hoặc vị trí các mục cài đặt có thể khác nhau tùy hãng điện thoại. Nếu không thấy mục cần tìm, dùng ô tìm kiếm trong Cài đặt hệ thống.

## Mở trình hướng dẫn

Mở **Mika › Cài đặt › Điều khiển điện thoại › Thiết lập điều khiển điện thoại**. Nếu đang làm một tác vụ cần dùng ứng dụng, bạn cũng có thể chạm **Mở Cài đặt** trong cuộc trò chuyện. Trình hướng dẫn kiểm tra trạng thái và đánh dấu từng bước khi hoàn tất.

## Các bước ghép nối

1. **Bật Tùy chọn nhà phát triển.** Mở **Cài đặt › Giới thiệu điện thoại**, tìm **Số bản dựng** và chạm nhanh 7 lần. Nhập mã khóa nếu điện thoại yêu cầu. Trên một số máy, Số bản dựng nằm trong mục Thông tin phần mềm.
2. **Bật Gỡ lỗi USB.** Trong **Tùy chọn nhà phát triển**, bật **Gỡ lỗi USB** và chấp thuận lời nhắc của hệ thống. Giữ mục này luôn bật để Mika tiếp tục hoạt động ổn định. Không đổi các công tắc khác nếu Mika không yêu cầu; một số mục có thể xóa dữ liệu điện thoại.
3. **Dịch vụ trợ năng (không bắt buộc).** Có thể bật Mika trong **Cài đặt › Trợ năng** để Mika tự đọc mã ghép nối. Nếu Android chặn quyền vì ứng dụng được cài ngoài cửa hàng, hãy bỏ qua bước này: Mika có thể bật dịch vụ sau khi ghép nối. Đây thường là cách đơn giản hơn.
4. **Bật Gỡ lỗi không dây.** Trong Tùy chọn nhà phát triển, bật **Gỡ lỗi không dây**. Khi được hỏi, chọn **Cho phép** và đánh dấu **Luôn cho phép trên mạng này**.
5. **Ghép nối bằng mã.** Mở trang Gỡ lỗi không dây, chạm **Ghép nối thiết bị bằng mã ghép nối**. Mika thường tự đọc mã sau vài giây. Nếu không, mở thông báo của Mika và nhập 6 chữ số trong khi cửa sổ ghép nối vẫn mở. Mã sẽ đổi mỗi lần mở cửa sổ.
6. **Chờ Mika kết nối.** Sau khi ghép nối thành công, Mika tự khởi động trợ lý điều khiển. Khi trang trạng thái báo **Đã kết nối**, bạn có thể bắt đầu giao việc.

## Sau khi khởi động lại điện thoại

Giữ **Gỡ lỗi USB** luôn bật. Sau khi điện thoại khởi động lại, kết nối Wi-Fi rồi bật lại **Gỡ lỗi không dây**; Mika sẽ tự kết nối với thiết bị đã ghép nối, không cần nhập mã mới.

## Khắc phục sự cố

- **Không tìm thấy Gỡ lỗi không dây:** một số hệ thống không cung cấp tính năng này. Có thể khởi chạy trợ lý từ máy tính qua USB; xem hướng dẫn tiếng Anh [Thiết lập điều khiển điện thoại](setup-guide.en.md) hoặc [Cài đặt với trợ lý trên máy tính](install-with-agent.en.md).
- **Không thấy thông báo nhập mã:** cho phép thông báo Mika trong cài đặt Android, mở lại cửa sổ ghép nối và lấy mã mới. Bạn cũng có thể dùng chế độ chia đôi màn hình để vừa xem mã vừa nhập.
- **Android chặn dịch vụ trợ năng:** mở **Thông tin ứng dụng của Mika**, chọn **Cho phép cài đặt bị hạn chế** nếu tùy chọn này có, rồi thử lại. Hoặc bỏ qua bước trợ năng; Mika sẽ tự bật sau khi ghép nối.
- **Không kết nối được:** kiểm tra điện thoại đang ở Wi-Fi, Gỡ lỗi không dây đang bật và cửa sổ ghép nối chưa đóng. Nếu cần, tắt rồi bật lại Gỡ lỗi không dây và ghép nối lại.
- **Không muốn cấp quyền điều khiển ứng dụng:** bạn có thể tiếp tục chỉ dùng trò chuyện, web và tệp; việc bỏ qua không ảnh hưởng các tính năng đó.

Mika dùng Gỡ lỗi không dây của Android để điều khiển màn hình ảo riêng. Hãy chỉ ghép nối trên điện thoại của bạn và không chia sẻ mã ghép nối hoặc token với người khác.
