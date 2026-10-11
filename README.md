# ai-anime3 — Bộ tag Danbooru + e621 bản tiếng Việt

Repo này chứa danh sách tag hợp nhất **Danbooru + e621** (nguồn:
`danbooru_e621_merged_2026-10-01_pt20-ia-dd-ed-spc.csv` của
[DraconicDragon/dbr-e621-lists-archive](https://github.com/DraconicDragon/dbr-e621-lists-archive))
ở 4 định dạng, kèm toàn bộ công cụ để tự sinh lại chúng.

## 🎨 Hệ thống tạo ảnh WAI-Illustrious v17 trên Colab

Thư mục [`colab/`](colab/) chứa trọn bộ hệ thống sinh ảnh chạy trên Google Colab, lấy
**chính kho tag đã dịch của repo này làm bộ nhắc prompt**:

| Thành phần | Nội dung |
|---|---|
| Bộ cài một ô ⭐ | [`colab/WAI_v17_1click.ipynb`](colab/WAI_v17_1click.ipynb) — bật GPU, chọn model ở dropdown, chạy một ô cài cả hệ thống |
| Notebook chi tiết | [`colab/WAI_Illustrious_v17_vi.ipynb`](colab/WAI_Illustrious_v17_vi.ipynb) — chạy từng bước, kèm ví dụ API |
| Model | WAI-illustrious-SDXL **v17.0** (SDXL 6,5 GB, VAE tích hợp sẵn), tải từ mirror HuggingFace không cần token, có kiểm SHA256 |
| Backend | **Forge Neo** (`Haoming02/sd-webui-forge-classic` nhánh `neo`) — đúng phần mềm thẻ model khuyến nghị |
| Bộ nhắc | Gõ tiếng Việt ngay trong ô prompt (tagcomplete đã cấu hình sẵn), hoặc dùng tab **“Prompt VN”** để tra tag, xếp thứ tự prompt chuẩn Illustrious/WAI, sinh negative và sinh ảnh |

Ba cách dùng kho prompt: **tagcomplete** (gõ `áo dài`, `tóc dài` ra tag tiếng Anh),
**tab Prompt VN** (tra cứu + gom 18 nhóm + dựng prompt có cấu trúc), và
**gọi API từ notebook** (sinh ảnh hàng loạt). App Gradio cũng chạy độc lập được ngoài
Colab: `python3 colab/prompt_builder.py --demo`.

**Bộ cài một lệnh:** [`colab/install.sh`](colab/install.sh), hướng dẫn trong
[`colab/INSTALL.md`](colab/INSTALL.md). Mặc định FP16 bản gốc; có chọn FP8/INT8/HSWQ
cộng đồng (thử nghiệm), chọn thư mục, kiểm SHA256, tải tiếp và chẩn đoán lỗi.
Mọi dữ liệu nằm trong `/content`, không tự mount Drive.

Chi tiết hệ thống/bộ dựng prompt: [`colab/README.md`](colab/README.md).

## Các file đầu ra

| File | Nội dung | Dùng để làm gì |
|---|---|---|
| `danbooru_e621.csv` | **Bản gốc**, byte-identical với file nguồn | Nạp vào sd-webui-tagcomplete để autocomplete ra tag tiếng Anh thật (prompt đúng chuẩn) |
| `danbooru_e621_nounderscore.csv` | Bản gốc nhưng **đã bỏ dấu `_`** (thay bằng khoảng trắng) ở cả cột tag lẫn cột aliases | Đọc/tìm kiếm dễ hơn, hoặc dùng cho công cụ hiển thị tag dạng có khoảng trắng |
| `danbooru_e621_vi.csv` | **Bản tiếng Việt**, vẫn 4 cột `tag,category,post_count,aliases`; cột aliases giữ nguyên tag tiếng Anh để tra ngược | Tra cứu ý nghĩa tag bằng tiếng Việt |
| `danbooru_e621_vi_translation.csv` | 2 cột `<English tag>,<Translation>` — **45.513 dòng**, chỉ gồm tag có bản dịch thật | Nạp vào **Translation filename** của sd-webui-tagcomplete: gõ/tìm bằng tiếng Việt vẫn ra tag tiếng Anh, và thấy nghĩa tiếng Việt trong danh sách gợi ý |

Ba file đầu: UTF-8, xuống dòng LF, **349.714 dòng**, không có dòng tiêu đề.

**Ngoại lệ duy nhất khi bỏ dấu `_`:** 26 tag là emoticon (`^_^`, `o_o`, `|_|`, `+_+`,
`._.`, `3_3`, `ಠ_ಠ`...) được **giữ nguyên dấu `_`**, vì ở đó `_` là nét vẽ của khuôn mặt
chứ không phải dấu ngăn cách từ — đổi thành `^ ^` sẽ làm hỏng tag. Các tag dạng tên
riêng có `_` (`h&k_g11` → `h&k g11`, `k_98` → `k 98`) vẫn bỏ `_` bình thường.
Danh sách emoticon nằm trong `EMOTICON_KEEP` của `tools/build_vi.py`.

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

| Category | Số tag | Từ điển | Quy tắc mẫu | Ghép đệ quy | Chưa dịch | Độ phủ (theo post_count) |
|---|---|---|---|---|---|---|
| 0 General (dbr) | 41.914 | 3.379 | 3.935 | 16.528 | 18.072 | **97,59%** |
| 5 Meta (dbr) | 605 | 392 | 133 | 23 | 57 | **99,74%** |
| 7 General (e621) | 34.518 | 1.382 | 5.045 | 14.718 | 13.373 | **97,09%** |
| 12 Species (e621) | 5.647 | 869 | 427 | 928 | 3.423 | **98,63%** |
| 14 Meta (e621) | 393 | 312 | 72 | 3 | 6 | **99,85%** |
| 15 Lore (e621) | 110 | 44 | 66 | 0 | 0 | **100%** |
| Tên riêng (1,3,4,8,9,10,11) | 266.527 | — | — | — | giữ nguyên, chỉ bỏ `_` |

Tag chưa dịch được giữ nguyên tiếng Anh (đã bỏ `_`). Đó gần như toàn bộ là tag rất hiếm
(post_count thấp, đuôi dài của phân phối) hoặc tên riêng của loài/nhân vật trong từng series.

Tổng cộng **45.513 tag** có bản dịch tiếng Việt thật; phần còn lại là tên riêng
(artist, copyright, character, 266.527 tag) vốn không dịch.

## Cách bản dịch được tạo

1. **Từ điển thủ công** (`tools/dict/`): `vi_general.py` (cat 0), `vi_e621.py` (cat 7),
   `vi_meta.py` (cat 5 + 14), `vi_species.py` (cat 12 + 15), `vi_extra.py`, `vi_extra2.py`,
   `vi_extra3.py`, `vi_extra4.py` (các đợt bổ sung tag tần suất cao còn sót, kèm bảng chú
   thích emoticon).
2. **Quy tắc mẫu** (`tools/vi_rules.py`): tự ghép bản dịch cho tag có cấu trúc đều đặn,
   chỉ khi **mọi** thành phần đều tra được — nên không sinh ra bản dịch sai:
   - `X_(lore)`, `A_and_B_(lore)` → "… (theo cốt truyện)"
   - tỉ lệ `16:9`, năm `2024`, `19th_century`
   - `X_(artwork)` / `X_(medium)` → "tác phẩm làm bằng X" / "chất liệu X"
   - `bad_X_link`, `X_sample`, `X_commentary`, `X_text`, `X_audio`, `X_description`
   - `X_request`, `check_X`, `has_X_revision`, `no_X`, `X_monochrome`, `A_and_B` (màu)
   - `màu + danh từ` (`red_eyes` → "mắt màu đỏ"), `số + danh từ`, `tính từ + danh từ`
     (`long_hair` → "tóc dài"), `A/B`, `A_and_B`, `A_on_B`, `A_penetrating_B`, `X_humanoid`
3. **Ghép đệ quy** (`tools/vi_compose.py` + `tools/dict/vi_vocab.py`): dịch tag tổ hợp
   chưa có trong từ điển bằng cách phân tích cấu trúc, theo thứ tự:
   - hậu tố ngoặc: `sword_(object)` → "kiếm (vật thể)"; tên riêng không dịch được vẫn giữ
     nguyên và chỉ dịch phần ngoặc: `hatsune_miku_(cosplay)` → "hatsune miku (cosplay)"
   - động từ đứng đầu: `holding_sword` → "cầm kiếm"; `wearing` tự chọn "đội/đeo/mang/mặc"
     theo loại trang phục (`wearing_hat` → "đội mũ", `wearing_gloves` → "mang găng tay")
   - lượng từ đứng trước: `multiple_girls` → "nhiều cô gái"
   - giới từ (kể cả giới từ ghép 2–3 chữ): `hand_on_head` → "bàn tay trên đầu",
     `head_out_of_frame` → "đầu ra ngoài khung hình", `after_rain` → "sau cơn mưa"
   - chủ–vị–tân: `female_rimming_male` → "nữ giới quan hệ bằng miệng ở hậu môn nam giới"
   - hậu tố trạng thái: `panties_removed` → "quần lót đã tháo ra"
   - bổ nghĩa + danh từ trung tâm, **đảo trật tự** theo tiếng Việt:
     `school_uniform` → "đồng phục trường học", `red_leather_jacket` → "áo khoác da thuộc đỏ",
     `long_sleeved_shirt` → "áo sơ mi có tay áo dài"
   - khử từ bị lặp ở chỗ nối: `deer_antlers` → "gạc hươu" (không phải "gạc hươu hươu")

   Chỉ ghép khi **mọi** mảnh đều tra được, nên không sinh bản dịch đoán mò.

4. **Hình vị** (`tools/dict/vi_morphemes.py` + `vi_vocab.py`): bảng màu sắc, kích thước,
   số đếm, ngôn ngữ, tên trang web, ~180 từ chỉ quan hệ gia đình/giới tính, và
   ~2.000 mục từ vựng phân loại theo vai trò ngữ pháp (danh từ / tính từ / động từ /
   lượng từ / hậu tố / giới từ) để phục vụ bước 2 và 3.

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
  vi_compose.py                      bộ ghép đệ quy cho tag tổ hợp
  source_merged_2026-10-01.csv       file nguồn (gitignored)
  dict/
    vi_general.py  vi_e621.py  vi_meta.py   vi_species.py
    vi_extra.py    vi_extra2.py vi_extra3.py vi_extra4.py vi_extra5.py
    vi_morphemes.py vi_vocab.py
  work/                              danh sách tag trung gian (gitignored)
colab/                               hệ thống tạo ảnh WAI-Illustrious v17 trên Colab
  WAI_v17_1click.ipynb               bộ cài Colab một ô + dropdown model
  install.sh                        bộ cài một lệnh, resume/verify/doctor
  INSTALL.md                        hướng dẫn bộ cài
  make_install_notebook.py           sinh notebook một ô
  WAI_Illustrious_v17_vi.ipynb        notebook chi tiết (mở trong Colab)
  setup_forge.sh                     script cài đặt theo từng stage
  prompt_builder.py                  app Gradio độc lập
  make_notebook.py                   script sinh file .ipynb
  make_tagcomplete_assets.py         sinh tag hệ thống + bản dịch gộp cho tagcomplete
  prompt_lib/                        thư viện lõi (index / groups / builder / system_tags)
  extension/vi-prompt-builder/       extension Forge: tab "Prompt VN"
  tests/test_prompt_lib.py           bộ kiểm tra hồi quy
  assets/  outputs/                  file sinh ra khi chạy (gitignored)
```

## Ghi chú về quy ước tên file nguồn

`pt20` = ngưỡng post_count 20 · `ia` = gồm alias đang hoạt động ·
`dd` = gồm alias Danbooru đã xoá · `ed` = gồm alias e621 đã xoá ·
`spc` = `post_count` là **tổng** của Danbooru + e621.
Repo nguồn cập nhật tag list mỗi quý (tháng 1, 4, 7, 10).
