# ai-anime3 — Bộ tag Danbooru + e621 bản tiếng Việt

Repo này chứa danh sách tag hợp nhất **Danbooru + e621** (nguồn:
`danbooru_e621_merged_2026-10-01_pt20-ia-dd-ed-spc.csv` của
[DraconicDragon/dbr-e621-lists-archive](https://github.com/DraconicDragon/dbr-e621-lists-archive))
ở 4 định dạng, kèm toàn bộ công cụ để tự sinh lại chúng.

## Các file đầu ra

| File | Nội dung | Dùng để làm gì |
|---|---|---|
| `danbooru_e621.csv` | **Bản gốc**, byte-identical với file nguồn | Nạp vào sd-webui-tagcomplete để autocomplete ra tag tiếng Anh thật (prompt đúng chuẩn) |
| `danbooru_e621_nounderscore.csv` | Bản gốc nhưng **đã bỏ dấu `_`** (thay bằng khoảng trắng) ở cả cột tag lẫn cột aliases | Đọc/tìm kiếm dễ hơn, hoặc dùng cho công cụ hiển thị tag dạng có khoảng trắng |
| `danbooru_e621_vi.csv` | **Bản tiếng Việt**, vẫn 4 cột `tag,category,post_count,aliases`; cột aliases giữ nguyên tag tiếng Anh để tra ngược | Tra cứu ý nghĩa tag bằng tiếng Việt |
| `danbooru_e621_vi_translation.csv` | 2 cột `<English tag>,<Translation>` — **15.290 dòng**, chỉ gồm tag có bản dịch thật | Nạp vào **Translation filename** của sd-webui-tagcomplete: gõ/tìm bằng tiếng Việt vẫn ra tag tiếng Anh, và thấy nghĩa tiếng Việt trong danh sách gợi ý |

Ba file đầu: UTF-8, xuống dòng LF, **349.714 dòng**, không có dòng tiêu đề.

> ⚠️ Với `danbooru_e621_vi.csv`, cột `tag` là tiếng Việt nên **không** dùng nó làm file
> autocomplete chính khi tạo ảnh — model không hiểu tag tiếng Việt. Dùng
> `danbooru_e621.csv` (hoặc `_nounderscore.csv`) để sinh ảnh, và dùng
> `danbooru_e621_vi_translation.csv` nếu muốn vừa gõ tag thật vừa thấy nghĩa tiếng Việt.

## Cách nạp vào sd-webui-tagcomplete (A1111 / Forge)

1. `Settings → Tag Autocomplete → Tag filename` → chọn `danbooru_e621.csv`.
2. `Settings → Tag Autocomplete → Translation filename` → chọn
   `danbooru_e621_vi_translation.csv`. Extension sẽ tự dịch tag **và alias**, đồng thời
   cho phép tìm kiếm bằng tiếng Việt (gõ `tóc dài` sẽ gợi ý `long_hair`).
   Giữ nguyên setting `Translation file uses old 3-column translation format` = **tắt**,
   vì file này dùng đúng định dạng 2 cột mới.
3. Trong tab **Extra Networks** của Tag Autocomplete, chọn bộ `danbooru_e621` nếu có sẵn,
   hoặc để mặc định — file merged dùng chung một cột category.

### Category trong file merged

Category của e621 được **cộng thêm 7** để không trùng với Danbooru.

| Category | Nhóm | Có dịch sang tiếng Việt? |
|---|---|---|
| 0 | General (Danbooru) | ✅ có |
| 1 | Artist (Danbooru) | ❌ tên riêng — chỉ bỏ `_` |
| 3 | Copyright (Danbooru) | ❌ tên riêng — chỉ bỏ `_` |
| 4 | Character (Danbooru) | ❌ tên riêng — chỉ bỏ `_` |
| 5 | Meta (Danbooru) | ✅ có |
| 7 | General (e621) | ✅ có |
| 8 | Artist (e621) | ❌ tên riêng — chỉ bỏ `_` |
| 9 | Contributor (e621) | ❌ tên riêng — chỉ bỏ `_` |
| 10 | Copyright (e621) | ❌ tên riêng — chỉ bỏ `_` |
| 11 | Character (e621) | ❌ tên riêng — chỉ bỏ `_` |
| 12 | Species (e621) | ✅ có |
| 14 | Meta (e621) | ✅ có |
| 15 | Lore (e621) | ✅ có |

Category 2, 6, 13 không hợp lệ nên không xuất hiện trong file.

## Độ phủ bản dịch

Đo theo **tổng `post_count`** của từng category (tag phổ biến quan trọng hơn tag hiếm):

| Category | Số tag | Dịch bằng từ điển | Dịch bằng quy tắc mẫu | Chưa dịch | Độ phủ (theo post_count) |
|---|---|---|---|---|---|
| 0 General (dbr) | 41.914 | 3.207 | 3.910 | 34.797 | **91,76%** |
| 5 Meta (dbr) | 605 | 392 | 133 | 80 | **99,73%** |
| 7 General (e621) | 34.518 | 1.247 | 4.894 | 28.377 | **90,01%** |
| 12 Species (e621) | 5.647 | 734 | 303 | 4.610 | **97,41%** |
| 14 Meta (e621) | 393 | 312 | 72 | 9 | **99,72%** |
| 15 Lore (e621) | 110 | 44 | 66 | 0 | **100%** |
| Tên riêng (1,3,4,8,9,10,11) | 266.527 | — | — | — | giữ nguyên, chỉ bỏ `_` |

Tag chưa dịch được giữ nguyên tiếng Anh (đã bỏ `_`). Đó gần như toàn bộ là tag rất hiếm
(post_count thấp, đuôi dài của phân phối) hoặc tên riêng của loài/nhân vật trong từng series.

## Cách bản dịch được tạo

1. **Từ điển thủ công** (`tools/dict/`): `vi_general.py` (cat 0), `vi_e621.py` (cat 7),
   `vi_meta.py` (cat 5 + 14), `vi_species.py` (cat 12 + 15), `vi_extra.py` /
   `vi_extra2.py` (bổ sung tag tần suất cao còn sót). Tổng **8.188 mục** không trùng.
2. **Quy tắc mẫu** (`tools/vi_rules.py`): tự ghép bản dịch cho tag có cấu trúc đều đặn,
   chỉ khi **mọi** thành phần đều tra được — nên không sinh ra bản dịch sai:
   - `X_(lore)`, `A_and_B_(lore)` → "… (theo cốt truyện)"
   - tỉ lệ `16:9`, năm `2024`, `19th_century`
   - `X_(artwork)` / `X_(medium)` → "tác phẩm làm bằng X" / "chất liệu X"
   - `bad_X_link`, `X_sample`, `X_commentary`, `X_text`, `X_audio`, `X_description`
   - `X_request`, `check_X`, `has_X_revision`, `no_X`, `X_monochrome`, `A_and_B` (màu)
   - `màu + danh từ` (`red_eyes` → "mắt màu đỏ"), `số + danh từ`, `tính từ + danh từ`
     (`long_hair` → "tóc dài"), `A/B`, `A_and_B`, `A_on_B`, `A_penetrating_B`, `X_humanoid`
3. **Hình vị** (`tools/dict/vi_morphemes.py`): bảng màu sắc, kích thước, số đếm, ngôn ngữ,
   tên trang web và ~180 từ chỉ quan hệ gia đình/giới tính để phục vụ bước 2.

### Sinh lại toàn bộ

```bash
python3 tools/build_vi.py
```

File nguồn nằm ở `tools/source_merged_2026-10-01.csv` (không commit — tải lại được bằng
lệnh dưới). Script in ra thống kê độ phủ sau khi chạy.

```bash
curl -sL -H "Accept: application/vnd.github.raw" \
  -o tools/source_merged_2026-10-01.csv \
  "https://api.github.com/repos/DraconicDragon/dbr-e621-lists-archive/contents/tag-lists/danbooru_e621_merged/danbooru_e621_merged_2026-10-01_pt20-ia-dd-ed-spc.csv"
```

### Thêm / sửa bản dịch

Mở file từ điển tương ứng trong `tools/dict/`, thêm dòng `"tag_gốc": "bản dịch"`,
rồi chạy lại `python3 tools/build_vi.py`. Không cần sửa tag gốc có `_` —
từ điển luôn dùng dạng tag gốc.

## Cấu trúc thư mục

```
danbooru_e621.csv                    bản gốc phục hồi
danbooru_e621_nounderscore.csv       bản bỏ dấu gạch dưới
danbooru_e621_vi.csv                 bản tiếng Việt (4 cột)
danbooru_e621_vi_translation.csv     bản dịch 2 cột cho tính năng Translation
tools/
  build_vi.py                        script sinh 4 file trên
  vi_rules.py                        bộ quy tắc dịch theo mẫu
  source_merged_2026-10-01.csv       file nguồn (gitignored)
  dict/
    vi_general.py  vi_e621.py  vi_meta.py  vi_species.py
    vi_extra.py    vi_extra2.py        vi_morphemes.py
  work/                              danh sách tag trung gian (gitignored)
```

## Ghi chú về quy ước tên file nguồn

`pt20` = ngưỡng post_count 20 · `ia` = gồm alias đang hoạt động ·
`dd` = gồm alias Danbooru đã xoá · `ed` = gồm alias e621 đã xoá ·
`spc` = `post_count` là **tổng** của Danbooru + e621.
Repo nguồn cập nhật tag list mỗi quý (tháng 1, 4, 7, 10).
