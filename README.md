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
| Bộ nhắc | Gõ tiếng Việt ngay trong ô prompt (tagcomplete đã cấu hình sẵn), hoặc mở accordion **“🇻🇳 Prompt tiếng Việt”** ngay trong tab **txt2img** để tra tag, chọn phong cách, xếp thứ tự prompt chuẩn Illustrious/WAI và đổ vào ô prompt |

Ba cách dùng kho prompt: **tagcomplete** (gõ `áo dài`, `tóc dài` ra tag tiếng Anh),
**accordion Prompt tiếng Việt trong tab txt2img** (tra cứu + gom 18 nhóm + dựng prompt có
cấu trúc rồi **Đưa vào txt2img**, dùng chính nút Generate của Forge — tab riêng
“Prompt VN” đã bỏ), và **gọi API từ notebook** (sinh ảnh hàng loạt). App Gradio đầy đủ
vẫn chạy độc lập được ngoài Colab: `python3 colab/prompt_builder.py --demo`.

**Bộ cài một lệnh:** [`colab/install.sh`](colab/install.sh), hướng dẫn trong
[`colab/INSTALL.md`](colab/INSTALL.md). Mặc định FP16 bản gốc; có chọn FP8/INT8/HSWQ
cộng đồng (thử nghiệm), chọn thư mục, kiểm SHA256, tải tiếp và chẩn đoán lỗi.
Mọi dữ liệu nằm trong `/content`, không tự mount Drive.

> **Mở lại link báo “No interface is running right now”?** Đó là trang của relay `gradio.live`, không phải Forge hỏng: link share hết hạn sau khoảng 10 phút–vài giờ, hoặc runtime Colab vừa restart nên Forge đã tạo link mới. Chạy `bash /content/install.sh --status` (báo link còn sống hay đã chết), rồi `bash /content/install.sh --only launch,verify --restart` và mở **link mới nhất**. [Chi tiết + bảng chẩn đoán](colab/INSTALL.md#no-interface-is-running-right-now-khi-mở-lại-link).

> **Bộ cài 1.0.7:** thêm **Ảnh đã tạo** trong app Gradio (trước đây cả tab Prompt VN): bảng + thumbnail phân trang, xem/tải ảnh gốc, dùng lại seed. Lịch sử ở SQLite trên đĩa, không gom toàn bộ PIL/base64 vào RAM; ảnh gốc/metadata giữ nguyên. [Cập nhật chỉ phần mềm](colab/INSTALL.md#bảng-ảnh-đã-tạo-107).

> **Bộ cài 1.0.6:** cài mới mặc định **Gradio share** (`gradio.live`), Cloudflare vẫn chọn được. Người dùng báo ảnh mở nhanh hơn/chưa lặp lại lỗi HTML→JSON sau khi đổi tunnel; không sửa model/chất lượng ảnh. Phiên Gradio share đang ổn **không cần restart/cài lại**. [Hướng dẫn tunnel](colab/INSTALL.md#ảnh-hiển-thị-chậm--unexpected-token--106).

> **Bộ cài 1.0.5:** đặt `MPLBACKEND=Agg` riêng cho Forge con, tránh backend inline Colab gây lỗi import Matplotlib/ControlNet/pandas Styler. [Ô cập nhật chỉ phần mềm](colab/INSTALL.md#error-hàng-loạt--matplotlib-backend-inline-colab-105), **không tải lại model/Torch**. Giữ schema/dropdown 1.0.4 và toàn bộ workflow/prompt.

> **Compat 1.0.4:** vá schema `/cmd-flags` của Neo (port integer, không HTTP 500) và khởi tạo sẵn choices/value của Checkpoint từ registry. Nếu API đã có WAI nhưng UI trống, [cập nhật phần mềm trong runtime hiện tại](colab/INSTALL.md#api-đã-có-wai-nhưng-dropdown-trống--cmd-flags-500-104), **không tải lại model/Torch**. Giữ các sửa prompt/quy trình 1.0.3 và checkpoint 1.0.2.

> **Quy trình 1.0.3:** thêm quy trình Nháp → Chuẩn → Hoàn thiện, seed ảnh đã chọn, sinh tuần tự tiết kiệm VRAM; sửa thay toàn cụm Việt → Anh mà không sót chữ Việt/mất tag khác. Giữ toàn bộ bản sửa checkpoint 1.0.2. [Hướng dẫn](colab/README.md#quy-trình-tối-ưu-bản-103) · [Rà soát checkpoint](colab/AUDIT.md).

**Chạy lại từ đầu:** [mở notebook Colab 1.0.7](https://colab.research.google.com/github/manhlee1196-boop/ai-anime3/blob/arena%2Fec9855a4-ai-anime3/colab/WAI_v17_1click.ipynb), chọn GPU T4 rồi **Run all**.
Notebook lấy bộ cài mới, chặn cache <1.0.7, đã tích hợp hướng dẫn thay Việt → Anh và
Nháp/Chuẩn/Hoàn thiện. Muốn runtime hoàn toàn mới, tải ảnh về trước khi **Disconnect
and delete runtime**; không có bước tự xóa dữ liệu/mount Drive.

Chi tiết hệ thống/bộ dựng prompt: [`colab/README.md`](colab/README.md).

## Các file đầu ra

| File | Nội dung | Dùng để làm gì |
|---|---|---|
| `danbooru_e621.csv` | **Bản gốc**, byte-identical với file nguồn | Nạp vào sd-webui-tagcomplete để autocomplete ra tag tiếng Anh thật (prompt đúng chuẩn) |
| `danbooru_e621_nounderscore.csv` | Bản gốc nhưng **đã bỏ dấu `_`** (thay bằng khoảng trắng) ở cả cột tag lẫn cột aliases | Đọc/tìm kiếm dễ hơn, hoặc dùng cho công cụ hiển thị tag dạng có khoảng trắng |
| `danbooru_e621_vi.csv` | **Bản tiếng Việt**, vẫn 4 cột `tag,category,post_count,aliases`; cột aliases giữ nguyên tag tiếng Anh để tra ngược | Tra cứu ý nghĩa tag bằng tiếng Việt |
| `danbooru_e621_vi_translation.csv` | 2 cột `<English tag>,<Translation>` — **45.557 dòng**, chỉ gồm tag có bản dịch thật | Nạp vào **Translation filename** của sd-webui-tagcomplete: gõ/tìm bằng tiếng Việt vẫn ra tag tiếng Anh, và thấy nghĩa tiếng Việt trong danh sách gợi ý |
| `style_tags.csv` | **506 tag phong cách vẽ** chia 9 nhóm, 6 cột `tag,vi,category,post_count,nhom,nguon_vi` — **dịch đủ 100%** | Chọn chất liệu/kỹ thuật/trường phái cho prompt; hướng dẫn, 12 công thức mẫu và mục chọn trong app ở [`STYLE_TAGS.md`](STYLE_TAGS.md) |

Ba file đầu: UTF-8, xuống dòng LF, **349.714 dòng**, không có dòng tiêu đề.

### Thẻ phong cách vẽ

[`style_tags.csv`](style_tags.csv) lọc ra **506 tag phong cách vẽ** từ chính kho tag trên —
chất liệu truyền thống, chất liệu số, kỹ thuật hoàn thiện (cel shading, line art, palette),
ánh sáng, trường phái mỹ thuật, phong cách thể loại, thời kỳ/thiết kế, và 229 tag `*_(style)`
của từng tác giả/series — **tất cả đã có nghĩa tiếng Việt** kèm số bài đăng để biết tag nào đủ mạnh.

**Chọn thẻ phong cách ngay trong app:** tab **🧩 Dựng prompt** → mục **“2. Chọn phong cách vẽ”**.
Mở ra là thấy **đủ 506 tag** (nhóm mặc định *Tất cả (506 tag — mọi nhóm)*, không tag nào bị ẩn);
chọn một nhóm để lọc, gõ ô tìm (không cần dấu) để lọc tiếp, hoặc chọn 1 trong 12 công thức sẵn —
tag của công thức được tick sẵn ở đầu danh sách còn các tag khác vẫn hiện. Tick xong bấm **➕ Thêm
tag phong cách**. Trong Forge, accordion **Prompt tiếng Việt** (tab txt2img) có đúng mục đó, và ô **Styles** có 12 style
`Phong cách — …` bấm là điền cả bộ tag.

Tài liệu [`STYLE_TAGS.md`](STYLE_TAGS.md) có 12 công thức prompt mẫu, lưu ý khi trộn chất liệu,
bảng độ mạnh của từng tag, và ghi lại các bản dịch đã sửa (`lego`, `spine_(medium)`, 41 tag thiếu…).

### Sinh ảnh không bị “treo”

Nút **🖼️ Sinh ảnh** cập nhật trạng thái mỗi giây lấy từ `/sdapi/v1/progress`
(`⏳ 01:12 · bước 9/25 · 36% · còn ~1m 20s`), có **⛔ Huỷ job** gọi `/sdapi/v1/interrupt`,
connect timeout 10 giây và read timeout 15 phút (`WAI_GEN_TIMEOUT`) thay cho một timeout
30 phút dùng chung. Forge đang bận job khác thì app báo rõ. Kẹt quá 90 giây không nhích
bước sẽ hiện cảnh báo kèm việc cần làm (thường là tắt Hires trên T4 16 GB). Nếu dòng trạng
thái đứng ở *“đã gửi prompt…”*, nút **🔎 Chẩn đoán** cho biết chính xác: Forge chưa bắt đầu
job, đang chạy nặng nên không trả lời kịp, hay thiếu endpoint tiến trình — kèm loại lỗi đọc
từ `forge.log`. Chi tiết: [`colab/INSTALL.md`](colab/INSTALL.md).

### Prompt dài mà không rơi chi tiết

CLIP chỉ đọc **75 token mỗi cửa sổ**; token càng xa đầu prompt càng ít trọng số, nên nhồi
200 token sẽ làm chi tiết ở nửa sau gần như mất tác dụng. App có sẵn công cụ đo và nén:
**📏 Đo độ dài prompt** (đếm token, chia cửa sổ, chỉ ra tag nào rơi vào vùng loãng) và
**✂️ Nén** (bỏ tag trùng nghĩa như `eyes` khi đã có `blue_eyes`). Ghi chú ngay dưới ô
positive hiện `🟢/🟡/🔴 N token · M cửa sổ · K tag` mỗi lần dựng prompt.

Ngân sách: ≤ 75 token = chắc · 76–150 = còn tốt · > 150 = bắt đầu loãng. Cách xử lý đầy đủ
(BREAK theo nhóm, prompt scheduling `[tag:0.4]`, hai lượt txt2img → img2img) ở
[`PROMPT_DAI.md`](PROMPT_DAI.md).

```bash
python3 tools/find_style_tags.py             # ghi lại style_tags.csv
python3 tools/find_style_tags.py --markdown  # in bảng Markdown như STYLE_TAGS.md
python3 tools/find_style_tags.py --check     # kiểm mọi tag có thật trong danbooru_e621.csv
python3 colab/tests/test_style_tags.py       # hồi quy
```

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
| 0 General (dbr) | 41.914 | 3.408 | 3.934 | 16.526 | 18.046 | **97,60%** |
| 5 Meta (dbr) | 605 | 407 | 118 | 23 | 57 | **99,74%** |
| 7 General (e621) | 34.518 | 1.400 | 5.040 | 14.723 | 13.355 | **97,10%** |
| 12 Species (e621) | 5.647 | 869 | 427 | 928 | 3.423 | **98,63%** |
| 14 Meta (e621) | 393 | 313 | 71 | 3 | 6 | **99,85%** |
| 15 Lore (e621) | 110 | 44 | 66 | 0 | 0 | **100%** |
| Tên riêng (1,3,4,8,9,10,11) | 266.527 | — | — | — | giữ nguyên, chỉ bỏ `_` |

Tag chưa dịch được giữ nguyên tiếng Anh (đã bỏ `_`). Đó gần như toàn bộ là tag rất hiếm
(post_count thấp, đuôi dài của phân phối) hoặc tên riêng của loài/nhân vật trong từng series.

Tổng cộng **45.557 tag** có bản dịch tiếng Việt thật; phần còn lại là tên riêng
(artist, copyright, character, 266.527 tag) vốn không dịch.

## Cách bản dịch được tạo

1. **Từ điển thủ công** (`tools/dict/`): `vi_general.py` (cat 0), `vi_e621.py` (cat 7),
   `vi_meta.py` (cat 5 + 14), `vi_species.py` (cat 12 + 15), `vi_extra.py`, `vi_extra2.py`,
   `vi_extra3.py`, `vi_extra4.py` (các đợt bổ sung tag tần suất cao còn sót, kèm bảng chú
   thích emoticon), `vi_style.py` (chất liệu / kỹ thuật / trường phái / ánh sáng — nhóm
   phong cách vẽ; đứng đầu bảng ưu tiên nên cũng dùng để **sửa** bản dịch sai như `lego`).
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
style_tags.csv                     506 tag phong cách vẽ (9 nhóm, kèm nghĩa VI)
STYLE_TAGS.md                       tài liệu tra cứu + công thức prompt phong cách
PROMPT_DAI.md                       cách giữ chi tiết khi prompt dài (CLIP 75 token)
tools/
  build_vi.py                        script sinh 4 file trên
  find_style_tags.py                 lọc tag phong cách vẽ -> style_tags.csv
  vi_rules.py                        bộ quy tắc dịch theo mẫu
  vi_compose.py                      bộ ghép đệ quy cho tag tổ hợp
  source_merged_2026-10-01.csv       file nguồn (gitignored)
  dict/
    vi_general.py  vi_e621.py  vi_meta.py   vi_species.py
    vi_extra.py    vi_extra2.py vi_extra3.py vi_extra4.py vi_extra5.py
    vi_style.py                         bản dịch + sửa bản dịch nhóm phong cách vẽ
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
  extension/vi-prompt-builder/       extension Forge: khối prompt Việt trong tab txt2img
  tests/test_prompt_lib.py           bộ kiểm tra hồi quy
  assets/  outputs/                  file sinh ra khi chạy (gitignored)
```

## Ghi chú về quy ước tên file nguồn

`pt20` = ngưỡng post_count 20 · `ia` = gồm alias đang hoạt động ·
`dd` = gồm alias Danbooru đã xoá · `ed` = gồm alias e621 đã xoá ·
`spc` = `post_count` là **tổng** của Danbooru + e621.
Repo nguồn cập nhật tag list mỗi quý (tháng 1, 4, 7, 10).
