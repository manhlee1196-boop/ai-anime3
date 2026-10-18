# 📱 Bản tối ưu cho trình duyệt điện thoại

Dùng Forge/Prompt VN bằng điện thoại (qua link `gradio.live` của Colab) thì giao
diện Gradio mặc định rất khó dùng: hai cột bị ép sát, nút nhỏ, ô nhập bị iOS tự
phóng to, bảng kết quả vỡ chữ. Bản tối ưu này sửa các điểm đó theo **10 mục** dưới
đây, áp dụng **tự động** cho cả ba bề mặt:

| Bề mặt | Nhận bản tối ưu bằng cách nào |
|---|---|
| Tab **Prompt VN** trong Forge | Forge tự nạp `extension/vi-prompt-builder/style.css` + `javascript/vi_mobile.js` (bộ cài chép sẵn) |
| Tab gốc **txt2img / img2img** của Forge | `style.css` là toàn cục trong trang Forge nên các mục chung (3, 4, 5 phần gợi ý tag, 7 nút Generate) cũng áp dụng |
| **App độc lập** `prompt_builder.py` | Nhận trực tiếp `mobile_css()`/`mobile_head()` từ `prompt_lib/mobile.py` (Gradio <6 qua `Blocks`, ≥6 qua `launch`) |

Một nguồn duy nhất là [`prompt_lib/mobile.py`](prompt_lib/mobile.py); hai file của
extension được sinh ra bằng `python3 colab/make_mobile_assets.py` (kiểm tra lệch:
`--check`). **Màn hình máy tính không thay đổi**: trừ vài quy tắc nền vô hại ở
Mục 1, mọi quy tắc đều nằm trong `@media (max-width: …)` hoặc `(pointer: coarse)`.

**Điểm gãy:** ≤900px xếp một cột · ≤640px hàng đôi xếp dọc · ≤480px điện thoại nhỏ.

---

## Mục 1 — Viewport, vùng an toàn và chống tràn ngang
- **Vấn đề:** trang bị cuộn ngang khó chịu; nút dính bị thanh home của iPhone che;
  chữ tự phóng to khi xoay ngang trên iOS.
- **Xử lý:** meta viewport có `viewport-fit=cover` (vẫn cho phép người dùng phóng
  to — không đặt `maximum-scale`), đệm `env(safe-area-inset-*)` cho máy tai thỏ,
  `overflow-x: clip` ở container, `min-width: 0` cho con của hàng flex (nguyên
  nhân tràn ngang số 1 của Gradio), `text-size-adjust: 100%`.
- **Kiểm chứng:** mở bằng điện thoại, vuốt ngang ở mép trang — trang không trượt ngang.

## Mục 2 — Bố cục một cột
- **Vấn đề:** cột “Tìm tag” và cột “Dựng prompt” (mỗi cột `scale=5`) bị ép còn
  ~170px trên màn hình 360px; cột Gradio còn có `min_width` mặc định 320px.
- **Xử lý:** ≤900px hai cột chính xếp dọc (tìm tag ở trên, dựng prompt ở dưới —
  đúng thứ tự thao tác), đặt `min_width=0` ngay trong code Python; ≤640px các
  hàng đôi (hai slider/dropdown cạnh nhau) cũng xếp dọc để kéo slider còn chính xác.
- **Kiểm chứng:** thu cửa sổ trình duyệt xuống dưới 900px, hai cột tự xếp dọc.

## Mục 3 — Cảm ứng
- **Vấn đề:** nút/link cao ~32px khó bấm trúng; núm slider nhỏ; chạm hai lần bị zoom.
- **Xử lý (chỉ thiết bị `pointer: coarse`):** nút/tab/select cao tối thiểu 48px
  (theo khuyến nghị vùng bấm của Apple/Google), núm slider 28px, checkbox/radio
  22px, mục trong dropdown cao ≥44px, `touch-action: manipulation` bỏ trễ chạm
  và zoom-chạm-hai-lần. Nút thumbnail trong gallery được loại trừ để không méo ảnh.
- **Kiểm chứng:** bấm thử các nút Tìm/Duyệt/Xoá bằng ngón cái — không cần ngắm.

## Mục 4 — Nhập liệu & bàn phím ảo
- **Vấn đề:** iOS Safari tự phóng to khi ô nhập có chữ <16px rồi không thu lại;
  bàn phím tự viết hoa/sửa chính tả làm hỏng tag (`ao_dai` → “Ao dai”); ô prompt
  dài chiếm hết màn hình.
- **Xử lý:** mọi ô nhập ≥16px ở ≤900px; textarea tối đa 45% chiều cao màn hình
  rồi cuộn trong ô; JS gắn `autocapitalize=none`, `autocorrect=off`,
  `spellcheck=false` cho ô tìm tag + ô prompt (kể cả ô prompt gốc của Forge),
  phím Enter trên bàn phím ảo hiện “Tìm” ở ô tìm tag và “Xong” ở ô prompt
  (`enterkeyhint`). Ô tìm tag vẫn gõ tiếng Việt có dấu bình thường.
- **Kiểm chứng:** chạm vào ô prompt trên iPhone — trang không nhảy zoom; gõ
  `ao_dai` không bị đổi thành “Ao dai”.

## Mục 5 — Bảng kết quả & danh sách gợi ý tag
- **Vấn đề:** bảng 5 cột (tag/nghĩa Việt/category/số ảnh/nhóm) bị ép cho chữ vỡ;
  dòng thấp khó bấm chọn; hộp gợi ý tagcomplete trong txt2img nhỏ và dài vô hạn.
- **Xử lý:** bảng giữ bề rộng đọc được (540px, máy nhỏ 460px) và **cuộn ngang có
  kiểm soát** trong khung của nó; cột **tag dính trái** khi cuộn để không lạc tag;
  dòng được đệm cao để bấm chọn; bật `wrap=True` để nghĩa tiếng Việt xuống dòng;
  hộp gợi ý tag bị giới hạn 45% chiều cao, mục gợi ý cao ≥44px (phần tagcomplete
  là *best-effort* vì tên class do extension đó quyết định — không khớp thì vô hại);
  bảng trong Markdown (tab hướng dẫn) cũng cuộn ngang thay vì tràn trang.
- **Kiểm chứng:** tìm “áo dài” → vuốt ngang trong bảng, cột tag vẫn đứng yên bên trái.

## Mục 6 — Ảnh & gallery
- **Vấn đề:** gallery kết quả cố định 480–520px chiều cao và 2 cột khiến ảnh dọc
  832×1216 bị thu nhỏ khó soi lỗi tay/mắt; thumbnail lịch sử 4 cột quá nhỏ để bấm.
- **Xử lý:** ≤900px gallery bỏ chiều cao cố định (tối đa 80% màn hình), kết quả
  2 cột, lịch sử 3 cột; ≤480px kết quả về **1 cột toàn bề rộng**, lịch sử 2 cột;
  ảnh gốc trong lịch sử `object-fit: contain` tối đa 70% chiều cao; JS gắn
  `loading=lazy` + `decoding=async` để ảnh ngoài màn hình không tranh băng thông 4G.
- **Kiểm chứng:** sinh một ảnh dọc rồi xem ở điện thoại — ảnh chiếm trọn bề rộng.

## Mục 7 — Nút hành động chính dính đáy
- **Vấn đề:** dựng xong prompt phải cuộn ngược lên tìm nút **Sinh ảnh**.
- **Xử lý:** ≤900px nút **Dựng prompt**/**Sinh ảnh** rộng 100%, cao 52px; nút
  Sinh ảnh `position: sticky` ở đáy (cộng vùng an toàn) trong lúc cuộn xem kết
  quả — dùng sticky thay vì fixed nên không che nội dung khi bàn phím ảo mở.
  Nút Generate và ô prompt của tab gốc Forge cũng được nâng tương tự.
- **Kiểm chứng:** cuộn xuống xem gallery, nút Sinh ảnh vẫn bám ở đáy màn hình.

## Mục 8 — Chữ & mật độ
- **Xử lý:** tiêu đề thu gọn (h1 22px, h2 19px, h3 16px) đỡ tốn diện tích dọc;
  chữ nội dung 15px; `code` (tag/prompt trong ghi chú) tự xuống dòng để đọc/chép
  được thay vì bị cắt ngang.

## Mục 9 — Hiệu năng trên máy yếu & mạng chậm
- **Xử lý:** tắt `backdrop-filter` (hiệu ứng mờ nền rất tốn GPU điện thoại) ở
  ≤900px; tôn trọng `prefers-reduced-motion` — tắt gần như mọi animation/chuyển
  cảnh nếu hệ điều hành yêu cầu; ảnh gallery lazy-load (Mục 6). Payload CSS/JS
  mobile chỉ ~11KB chưa nén, tải một lần cùng trang, không thêm request nền.
- **Giới hạn thật:** phần nặng trên điện thoại vẫn là chính Gradio/Forge và ảnh
  PNG gốc; mục này chỉ bỏ chi phí trình bày thừa, không nén được ảnh gốc (ảnh
  gốc giữ nguyên theo thiết kế của bảng Ảnh đã tạo).

## Mục 10 — Khả dụng & nằm ngang
- **Xử lý:** vòng `:focus-visible` rõ 3px cho người dùng bàn phím rời/phím
  chuyển (switch control); khi nằm ngang, textarea hạ xuống 35% và gallery nới
  lên 85% chiều cao để tận dụng màn hình thấp-rộng.

---

## Bật/tắt & cập nhật

- **Mặc định bật** ở mọi bản cài mới. Phiên Colab đang chạy chỉ cần cập nhật
  phần mềm (không tải lại model/Torch): đợi sinh ảnh xong rồi chạy ô cập nhật
  trong [INSTALL.md](INSTALL.md#bảng-ảnh-đã-tạo-107)
  (`--only extras,launch,verify --restart`) bằng code mới; `extras_ready` nay
  đòi cả `style.css`/`vi_mobile.js` nên bản cài cũ tự chạy lại stage `extras`.
  Nếu code mới còn ở nhánh tính năng chưa gộp, truyền thêm
  `--branch <nhánh-chứa-bản-tối-ưu>` cho bộ cài (hoặc sửa biến `BRANCH` trong ô
  notebook) để Colab lấy đúng code đó thay vì nhánh mặc định.
- **Tắt ở app độc lập:** `--no-mobile` hoặc biến môi trường `WAI_MOBILE_OPT=0`.
- **Tắt trong Forge:** đổi tên/xoá `extensions/vi-prompt-builder/style.css` và
  `javascript/vi_mobile.js` rồi khởi động lại Forge (lần chạy bộ cài `extras`
  tiếp theo sẽ chép lại nếu repo vẫn còn hai file này).
- **Sửa bản tối ưu:** chỉ sửa `prompt_lib/mobile.py` rồi chạy
  `python3 colab/make_mobile_assets.py`; đừng sửa tay `style.css`/`vi_mobile.js`.

## Kiểm tra tự động

```bash
python3 colab/tests/test_mobile.py        # 9 nhóm: đủ 10 mục, desktop không đổi,
                                          # đồng bộ file sinh, móc UI, bộ cài, JS (node --check)
python3 colab/make_mobile_assets.py --check
python3 colab/tests/test_prompt_ui.py     # dựng thử cả hai UI với Gradio thật (không cần GPU)
```

Chưa kiểm chứng trên thiết bị thật trong môi trường phát triển này (không có
điện thoại/trình duyệt thật): hãy mở link `gradio.live` bằng điện thoại, hoặc
F12 → Device Toolbar trên Chrome máy tính, và đi qua các dòng “Kiểm chứng” ở
từng mục. Selector chỉ dựa vào class `wai-*` của chính repo và phần tử HTML
chuẩn, không dựa vào class băm `svelte-…` nên bền qua các bản Gradio 4/5/6;
riêng lưới gallery dùng selector lưới tốt nhất có thể (`[class*="grid"]`) —
nếu một bản Gradio đổi cấu trúc gallery, phần còn lại của 10 mục vẫn hoạt động.
