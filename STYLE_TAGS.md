# Thẻ phong cách vẽ trong kho Danbooru + e621

Kết quả **kiểm tra trực tiếp** hai file dữ liệu của repo:

| File kiểm tra | Số dòng |
|---|---|
| `danbooru_e621.csv` (tag, category, post_count, aliases) | 349.714 tag |
| `danbooru_e621_vi_translation.csv` (tag, nghĩa tiếng Việt) | 45.557 bản dịch |

> **Kết quả: 506 tag phong cách vẽ**, chia **9 nhóm** — **tất cả 506 tag đều đã có bản dịch
> tiếng Việt** (đã sửa 41 tag thiếu + 16 tag dịch sai, xem [mục 3](#3-đã-sửa-những-gì)).
> Danh sách đầy đủ ở [`style_tags.csv`](style_tags.csv); bảng dưới in toàn bộ 8 nhóm đầu và
> 40 tag đầu của nhóm phong cách tác giả.
>
> **Chọn trong app:** tab **🧩 Dựng prompt** → mục **“2. Chọn phong cách vẽ”** (nhóm / công thức
> sẵn / ô tìm) → tick tag → **➕ Thêm tag phong cách**. Trong Forge: tab **Prompt VN** có đúng mục
> đó, và ô **Styles** có 12 style “Phong cách — …” bấm là ăn ngay.

Mỗi dòng trong `style_tags.csv` có 6 cột:

| Cột | Nghĩa |
|---|---|
| `tag` | tag tiếng Anh đúng như trong kho (dùng thẳng trong prompt) |
| `vi` | nghĩa tiếng Việt lấy từ `danbooru_e621_vi_translation.csv` |
| `category` | category trong file merged (0 General Danbooru, 5 Meta Danbooru, 7 General e621, 14 Meta e621…) |
| `post_count` | số ảnh dùng tag — càng cao model càng "hiểu" tag |
| `nhom` | một trong 9 nhóm bên dưới |
| `nguon_vi` | `csv` = dịch sẵn trong repo; `goi_y` = repo chưa dịch, nghĩa là gợi ý của tài liệu này |

---

## 1. Cách dùng nhanh trong prompt (WAI-Illustrious v17)

Thứ tự khuyến nghị — **phong cách đứng gần cuối**, sau trang phục/bối cảnh và trước hoạ sĩ:

```
chất lượng → phân loại → mô tả → chủ thể → nhân vật/series → ngoại hình
→ trang phục → biểu cảm/tư thế → bối cảnh → PHONG CÁCH → hoạ sĩ → meta
```

Ba câu chốt:

1. **Một công thức = 1 chất liệu + 1 kỹ thuật + (tuỳ chọn) 1 ánh sáng.** Nhiều hơn thì model
   trung bình hoá các tag và ra ảnh "nhựa", mất chất.
2. **Đừng trộn hai chất liệu đối kháng**: `watercolor_(medium)` + `3d_(artwork)` sẽ ra ảnh
   lai không giống cái nào.
3. **Tag càng ít ảnh càng yếu.** Trong ảnh hưởng thực tế: trên 10.000 bài là rất mạnh,
   1.000–10.000 là rõ, dưới 300 gần như không ăn (model chưa thấy đủ).

### Công thức mẫu (12 công thức có sẵn trong app)

Đây đúng là 12 công thức ở mục **2. Chọn phong cách vẽ** của app và 12 style
`Phong cách — …` trong ô **Styles** của Forge:

| Công thức (bấm được trong app) | Tag | Chất |
|---|---|---|
| **Tranh màu nước** | `watercolor_(medium)`, `traditional_media_(artwork)`, `painterly`, `soft_lighting` | chất lỏng, loang màu, viền mềm |
| **Anime cel-shading (TV)** | `anime_coloring`, `cel_shading`, `flat_colors`, `line_art` | nét sạch, màu phẳng, đúng chất anime truyền hình |
| **Anime thập niên 1990** | `1990s_(style)`, `retro_artstyle`, `cel_shading`, `retro_anime_style` | nét mảnh, màu bết kiểu VHS |
| **Tranh khắc gỗ Nhật** | `ukiyo-e`, `sumi-e`, `ink_wash_painting`, `nihonga` | mảng phẳng, mực loang, viền đậm |
| **Art Nouveau / kính màu** | `art_nouveau`, `stained_glass`, `painterly` | đường cong trang trí, viền chì |
| **Tranh sơn dầu cổ điển** | `oil_painting_(medium)`, `painterly`, `impasto`, `chiaroscuro` | dày màu, tương phản sáng tối mạnh |
| **3D / CG** | `3d_(artwork)`, `blender_(artwork)`, `photorealistic`, `rim_lighting` | khối, phản sáng — nhớ bỏ nếu muốn 2D |
| **Pixel art game cũ** | `pixel_art`, `pixel_animation`, `limited_palette`, `dithering` | điểm ảnh rõ, bảng màu hẹp |
| **Truyện tranh đen trắng** | `comic`, `greyscale`, `screentone`, `hatching` | khung truyện, tông chấm, nét gạch |
| **Phác thảo chì** | `sketch`, `graphite_(medium)`, `hatching`, `monochrome` | nét nháp, chưa tô màu |
| **Anime hiện đại chi tiết** | `anime_style`, `soft_shading`, `detailed_shading`, `high_contrast` | bóng mềm nhiều lớp, độ chi tiết cao |
| **Hoạt hình cổ (rubber hose)** | `toon_(style)`, `rubber_hose_style`, `fleischer_style_toon` | nét tròn, không khớp nối, kiểu 1930 |

### Mục chọn phong cách trong app / Forge

| Chỗ bấm | Cách dùng |
|---|---|
| App Gradio → tab **🧩 Dựng prompt** → **2. Chọn phong cách vẽ** | chọn **Nhóm** (9 nhóm) hoặc **Công thức sẵn**; gõ ô tìm (`màu nước`, `nuoc`, `ukiyo`) để lọc; tick tag rồi bấm **➕ Thêm tag phong cách** |
| Forge → tab **Prompt VN** | cùng mục, thêm nút **➕ Thêm tag phong cách** ngay trên ô “Tag đã chọn” |
| Forge → ô **Styles** (góc dưới ô prompt) | 12 style `Phong cách — Tranh màu nước`, `Phong cách — Pixel art game cũ`… bấm là điền cả bộ tag |
| Bảng “Độ mạnh của từng tag” | mỗi tag kèm số bài đăng và mức **rất mạnh / rõ / yếu / rất yếu** để biết tag nào thực sự ăn |

Bảng xếp hạng độ mạnh: ≥ 10.000 ảnh = rất mạnh · 1.000–9.999 = rõ · 300–999 = yếu ·
< 300 = rất yếu (xem cột `post_count` trong `style_tags.csv`).

### Lưu ý riêng của tag

- **`X_(medium)` vs `X_(artwork)`**: hậu tố `_(medium)` = "vẽ *bằng* chất liệu đó" (mạnh hơn khi
  muốn đổi chất liệu); `_(artwork)` = "bức này *là* tác phẩm thuộc loại đó". Cùng nghĩa tiếng Việt
  nhưng khác tác dụng — ưu tiên `_(medium)` khi muốn đổi chất.
- **`X_(style)`**: phong cách của một hoạ sĩ hoặc một series. Rất mạnh, chỉ nên dùng **một** tag;
  khi nhái series khác thì thêm `style_parody`. Đầy đủ 230 tag ở [mục 2.9](#29-phong-cách-tác-giả--series-230-tag).
- **`official_style`**: vẽ theo đúng phong cách chính thức của series, khác `official_art`
  (ảnh do chính tác giả/NXB phát hành — đây là tag *nguồn*, không phải tag điều khiển).
- **`monochrome` / `greyscale` / `sepia` / `spot_color`** đổi *toàn bộ* màu ảnh; nếu chỉ muốn
  nét đen trắng thì dùng `line_art` + `monochrome` chứ đừng dùng `greyscale` (dễ bị xám bệt).
- Trọng số: `(watercolor_(medium):1.15)` để nhấn, `(cel_shading:0.8)` khi bị phẳng quá.
- Muốn **tránh** một phong cách thì đưa vào negative (ví dụ `3d, photorealistic` trong negative
  để tránh ảnh trông như 3D).
- Forge/Illustrious coi `watercolor_(medium)` và `watercolor (medium)` như nhau; cứ dán nguyên
  dấu `_` từ CSV cho chắc.

---

## 2. Bảng theo nhóm

Cột **Bài đăng** là `post_count` thật trong `danbooru_e621.csv`.
Dấu `*` sau nghĩa = tag chưa có bản dịch trong repo, nghĩa là gợi ý.

### 2.1 Chất liệu truyền thống (68 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `traditional_media_(artwork)` | tác phẩm vẽ tay truyền thống | 87.150 |
| `painting_(artwork)` | tranh vẽ | 53.229 |
| `painting_(medium)` | tranh vẽ | 31.687 |
| `watercolor_(medium)` | màu nước | 22.905 |
| `marker_(medium)` | bút dạ | 18.600 |
| `graphite_(artwork)` | than chì | 18.579 |
| `graphite_(medium)` | than chì | 13.646 |
| `traditional_painting_(artwork)` | tranh vẽ tay truyền thống | 7.995 |
| `colored_pencil_(medium)` | bút chì màu | 7.659 |
| `stained_glass` | kính màu | 6.971 |
| `pen_(medium)` | bút mực | 6.573 |
| `sculpture` | tượng điêu khắc | 6.285 |
| `watercolor_(artwork)` | màu nước | 6.084 |
| `pen_(artwork)` | bút mực | 5.894 |
| `marker_(artwork)` | bút dạ | 4.969 |
| `traditional_watercolor_(artwork)` | màu nước truyền thống | 4.747 |
| `lego` | xếp hình Lego | 3.662 |
| `ink` | mực | 3.552 |
| `colored_pencil_(artwork)` | bút chì màu | 3.521 |
| `acrylic_paint_(medium)` | màu acrylic | 2.970 |
| `origami` | nghệ thuật gấp giấy | 2.932 |
| `millipen_(medium)` | bút kim millipen | 2.482 |
| `embroidery` | thêu | 2.180 |
| `oil_painting_(medium)` | sơn dầu | 1.803 |
| `nib_pen_(medium)` | bút ngòi chấm mực | 1.559 |
| `spray_paint` | sơn xịt | 1.534 |
| `ballpoint_pen_(medium)` | bút bi | 1.074 |
| `oil_painting_(artwork)` | sơn dầu | 978 |
| `watercolor_pencil_(medium)` | bút chì màu nước | 838 |
| `calligraphy_brush_(medium)` | bút lông thư pháp | 836 |
| `pastel_(medium)` | màu pastel | 748 |
| `papercraft_(medium)` | mô hình giấy | 600 |
| `acrylic_painting_(artwork)` | tranh acrylic | 551 |
| `gouache_(artwork)` | màu gouache | 455 |
| `tapestry` | thảm dệt treo tường | 431 |
| `collage_(artwork)` | tranh cắt dán | 381 |
| `collage_(medium)` | tranh cắt dán | 368 |
| `color_ink_(medium)` | mực màu | 354 |
| `crayon_(artwork)` | bút sáp | 337 |
| `gouache_(medium)` | màu gouache | 301 |
| `simulated_traditional_(artwork)` | giả chất liệu truyền thống | 259 |
| `sculpture_(artwork)` | tác phẩm điêu khắc | 227 |
| `charcoal_(artwork)` | than vẽ | 193 |
| `pastel_(artwork)` | màu pastel | 191 |
| `paper_cutout_(medium)` | cắt giấy | 164 |
| `chalk_(artwork)` | phấn | 162 |
| `mosaic` | tranh khảm | 147 |
| `kirigami` | nghệ thuật cắt giấy (kirigami) | 132 |
| `crayon_(medium)` | bút sáp | 122 |
| `lithograph_(artwork)` | bản in thạch bản | 111 |
| `brush_(medium)` | cọ vẽ | 109 |
| `airbrush_(medium)` | vẽ bằng cọ phun (airbrush) | 82 |
| `charcoal_(medium)` | than vẽ | 81 |
| `acrylic_gouache_(medium)` | màu acrylic gouache | 71 |
| `clay_(medium)` | chất liệu đất sét | 69 |
| `felt_(medium)` | vải nỉ | 68 |
| `engraving_(medium)` | tranh khắc (engraving) | 56 |
| `woodcut_(artwork)` | tranh khắc gỗ | 44 |
| `papercutting_(artwork)` | nghệ thuật cắt giấy | 41 |
| `amigurumi_(medium)` | thú bông móc len | 40 |
| `ink_(artwork)` | tranh vẽ bằng mực | 40 |
| `clay_(artwork)` | tác phẩm làm bằng đất sét | 35 |
| `engraving_(artwork)` | bản khắc | 29 |
| `chalk_(medium)` | phấn | 24 |
| `digital_pastel_(artwork)` | phấn tiên kỹ thuật số | 22 |
| `etching_(artwork)` | tranh khắc axit (etching) | 22 |
| `fudepen_(medium)` | bút lông nước Nhật (fudepen) | 22 |
| `embroidery_(medium)` | tranh thêu | 21 |

### 2.2 Chất liệu số & CG (78 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `digital_media_(artwork)` | tác phẩm kỹ thuật số | 1.803.089 |
| `photoshop_(medium)` | làm bằng Photoshop | 709.807 |
| `digital_drawing_(artwork)` | tranh vẽ kỹ thuật số | 346.613 |
| `3d_(artwork)` | tác phẩm 3D | 261.356 |
| `source_filmmaker_(artwork)` | làm bằng Source Filmmaker | 57.680 |
| `blender_(artwork)` | làm bằng Blender | 43.650 |
| `digital_painting_(artwork)` | tranh tô kỹ thuật số | 42.368 |
| `pixel_art` | nghệ thuật điểm ảnh | 32.033 |
| `pixel_(artwork)` | nghệ thuật điểm ảnh | 22.090 |
| `painttool_sai_(medium)` | vẽ bằng PaintTool SAI | 14.476 |
| `blender_cycles_(artwork)` | kết xuất bằng Blender Cycles | 13.600 |
| `clip_studio_paint_(medium)` | vẽ bằng Clip Studio Paint | 13.492 |
| `pixel_animation` | hoạt hình điểm ảnh | 8.812 |
| `procreate_(medium)` | vẽ bằng Procreate | 8.175 |
| `adobe_photoshop_(artwork)` | vẽ bằng Adobe Photoshop | 7.711 |
| `clip_studio_paint_(artwork)` | vẽ bằng Clip Studio Paint | 4.582 |
| `blender_(medium)` | làm bằng Blender | 4.392 |
| `paint.net_(medium)` | vẽ bằng Paint.NET | 3.337 |
| `microsoft_paint_(artwork)` | vẽ bằng Microsoft Paint | 3.085 |
| `blender_eevee_(artwork)` | kết xuất bằng Blender Eevee | 2.959 |
| `procreate_(artwork)` | vẽ bằng Procreate | 2.636 |
| `krita_(artwork)` | vẽ bằng Krita | 2.390 |
| `low_poly` | đồ hoạ đa giác thấp (low-poly) | 2.237 |
| `gimp_(medium)` | vẽ bằng GIMP | 2.215 |
| `ibispaint_(medium)` | vẽ bằng ibisPaint | 2.115 |
| `paint_tool_sai_(artwork)` | vẽ bằng PaintTool SAI | 2.087 |
| `vector_trace` | đồ lại theo vector | 2.039 |
| `ibispaint_(artwork)` | vẽ bằng ibisPaint | 1.987 |
| `koikatsu_(medium)` | tạo bằng Koikatsu | 1.324 |
| `microsoft_paint_(medium)` | vẽ bằng Microsoft Paint | 1.202 |
| `mikumikudance_(medium)` | làm bằng MikuMikuDance | 1.170 |
| `zbrush_(artwork)` | làm bằng ZBrush | 768 |
| `krita_(medium)` | vẽ bằng Krita | 760 |
| `medibang_paint_(artwork)` | vẽ bằng MediBang Paint | 739 |
| `autodesk_3ds_max_(artwork)` | làm bằng Autodesk 3ds Max | 723 |
| `spine_(medium)` | phần mềm Spine 2D | 721 |
| `autodesk_maya_(artwork)` | làm bằng Autodesk Maya | 601 |
| `flipnote_studio_(artwork)` | vẽ bằng Flipnote Studio | 578 |
| `daz_studio_(artwork)` | tác phẩm làm bằng Daz Studio | 511 |
| `drawpile_(artwork)` | vẽ chung trên Drawpile | 491 |
| `cinema_4d_(artwork)` | làm bằng Cinema 4D | 478 |
| `substance_painter_(artwork)` | tô chất liệu bằng Substance Painter | 382 |
| `zbrush_(medium)` | làm bằng ZBrush | 371 |
| `firealpaca_(artwork)` | vẽ bằng FireAlpaca | 302 |
| `ascii_art` | tranh bằng ký tự | 296 |
| `flipaclip_(artwork)` | vẽ bằng FlipaClip | 294 |
| `medibang_paint_(medium)` | vẽ bằng MediBang Paint | 282 |
| `inkscape_(artwork)` | vẽ bằng Inkscape | 272 |
| `flipnote_studio_(medium)` | vẽ bằng Flipnote Studio | 258 |
| `aseprite_(medium)` | vẽ bằng Aseprite | 233 |
| `vector_art` | tranh vector | 208 |
| `aseprite_(artwork)` | vẽ bằng Aseprite | 194 |
| `wigglypaint_(artwork)` | vẽ bằng WigglyPaint | 192 |
| `gimp_(artwork)` | vẽ bằng GIMP | 170 |
| `sketchbook_(artwork)` | sổ phác thảo | 139 |
| `unreal_engine_(artwork)` | làm bằng Unreal Engine | 99 |
| `paint.net_(artwork)` | vẽ bằng Paint.NET | 98 |
| `opencanvas_(medium)` | vẽ bằng OpenCanvas | 95 |
| `adobe_illustrator_(medium)` | vẽ bằng Adobe Illustrator | 94 |
| `piskel_(artwork)` | vẽ bằng Piskel | 82 |
| `marmoset_toolbag_(artwork)` | kết xuất bằng Marmoset Toolbag | 80 |
| `adobe_illustrator_(artwork)` | vẽ bằng Adobe Illustrator | 78 |
| `unity_(artwork)` | làm bằng Unity | 74 |
| `rebelle_(artwork)` | vẽ bằng Rebelle | 67 |
| `artrage_(artwork)` | vẽ bằng ArtRage | 62 |
| `autodesk_sketchbook_(medium)` | vẽ bằng Autodesk Sketchbook | 60 |
| `art_academy_(artwork)` | vẽ bằng Art Academy | 56 |
| `firealpaca_(medium)` | vẽ bằng FireAlpaca | 55 |
| `live2d_cubism_(artwork)` | làm bằng Live2D Cubism | 49 |
| `art_academy_(medium)` | vẽ bằng Art Academy | 48 |
| `paintstorm_(artwork)` | vẽ bằng PaintStorm | 47 |
| `dotpict_(medium)` | vẽ bằng Dotpict | 39 |
| `voxel_art` | nghệ thuật khối voxel | 33 |
| `blockbench_(medium)` | vẽ bằng Blockbench | 30 |
| `tvpaint_(artwork)` | vẽ bằng TVPaint | 24 |
| `corel_painter_(artwork)` | vẽ bằng Corel Painter | 23 |
| `toon_boom_harmony_(artwork)` | làm bằng Toon Boom Harmony | 23 |
| `moho_(artwork)` | làm bằng Moho | 21 |

### 2.3 Kỹ thuật hoàn thiện (58 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `monochrome` | đơn sắc | 1.359.875 |
| `greyscale` | thang xám | 791.939 |
| `sketch` | phác thảo | 394.471 |
| `shaded` | có đổ bóng | 279.011 |
| `colored` | đã tô màu | 169.594 |
| `outline` | đường viền nét | 123.456 |
| `spot_color` | điểm xuyết màu | 72.561 |
| `white_outline` | viền nét trắng | 72.056 |
| `anime_coloring` | tô màu kiểu anime | 57.537 |
| `highlights_(coloring)` | mảng sáng màu | 47.169 |
| `flat_colors` | màu phẳng | 31.108 |
| `line_art` | nét vẽ | 29.451 |
| `partially_colored` | có màu một phần | 26.836 |
| `limited_palette` | bảng màu giới hạn | 26.705 |
| `cel_shading` | đổ bóng kiểu cel | 24.118 |
| `halftone` | chấm tram (halftone) | 23.650 |
| `soft_shading` | đổ bóng mềm | 18.370 |
| `lineart` | nét vẽ | 16.766 |
| `colored_sketch` | phác thảo có màu | 14.508 |
| `hatching_(texture)` | đánh bóng bằng nét (texture) | 14.323 |
| `sepia` | màu nâu cổ | 14.091 |
| `flat_color` | màu phẳng | 13.927 |
| `greyscale_with_colored_background` | thang xám với phông nền có màu | 13.610 |
| `simple_shading` | đổ bóng đơn giản | 13.263 |
| `restricted_palette` | bảng màu giới hạn | 13.175 |
| `painterly` | nét vẽ kiểu hội hoạ | 11.021 |
| `black_outline` | viền nét đen | 7.268 |
| `screentones` | chấm tram truyện tranh (screentones) | 5.905 |
| `no_lineart` | không có nét viền | 5.384 |
| `high_contrast` | độ tương phản cao | 5.378 |
| `hatching_(art)` | đánh bóng bằng nét | 4.926 |
| `pastel_colors` | màu pastel | 4.822 |
| `linear_hatching` | đánh bóng bằng nét thẳng song song | 4.732 |
| `dithering` | kỹ thuật chấm pha điểm ảnh | 3.292 |
| `colored_line_art` | nét vẽ có màu | 3.283 |
| `multiple_monochrome` | nhiều hình đơn sắc | 2.022 |
| `thick_lineart` | nét vẽ dày | 1.921 |
| `sketchy` | dạng phác thảo | 1.891 |
| `screentone` | chấm tram truyện tranh (screentone) | 1.842 |
| `crosshatching` | đánh bóng nét chéo | 1.713 |
| `gradient` | chuyển sắc | 1.176 |
| `neon_palette` | bảng màu neon | 1.117 |
| `cross-hatching` | đánh bóng chéo nét | 797 |
| `thick_outlines` | nét viền dày | 657 |
| `cel_rendering` | render kiểu cel | 559 |
| `impasto` | kỹ thuật sơn dày (impasto) | 541 |
| `hatching` | đánh bóng bằng nét | 508 |
| `realistic_shading` | đổ bóng thực tế | 449 |
| `chiaroscuro` | tương phản sáng tối mạnh (chiaroscuro) | 441 |
| `no_shading` | không có đổ bóng | 400 |
| `stippling` | chấm điểm tạo bóng | 320 |
| `colored_outline` | đường viền nét có màu | 221 |
| `detailed_shading` | đổ bóng chi tiết | 159 |
| `halftone_shading` | đổ bóng chấm tram (halftone) | 128 |
| `complex_shading` | đổ bóng phức tạp | 127 |
| `flat_shading` | đổ bóng phẳng | 93 |
| `minimal_shading` | đổ bóng tối giản | 36 |
| `stylized_shading` | đổ bóng cách điệu | 30 |

### 2.4 Ánh sáng (10 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `backlighting` | ngược sáng | 49.081 |
| `lighting` | ánh sáng | 31.135 |
| `dappled_sunlight` | nắng lốm đốm | 15.274 |
| `sidelighting` | ánh sáng chiếu ngang | 13.411 |
| `underlighting` | ánh sáng chiếu từ dưới | 1.316 |
| `realistic_lighting` | ánh sáng thực tế | 527 |
| `dramatic_lighting` | ánh sáng kịch tính | 513 |
| `soft_lighting` | ánh sáng mềm | 300 |
| `mood_lighting` | ánh sáng theo tâm trạng | 226 |
| `rim_lighting` | ánh sáng viền | 151 |

### 2.5 Trường phái & mỹ thuật (21 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `surreal` | siêu thực | 6.672 |
| `abstract` | trừu tượng | 5.341 |
| `art_nouveau` | trường phái Art Nouveau | 2.946 |
| `psychedelic` | phong cách ảo giác | 1.481 |
| `abstract_art` | nghệ thuật trừu tượng | 1.270 |
| `nihonga` | tranh Nhật hiện đại (nihonga) | 1.268 |
| `surrealism` | trường phái Siêu thực | 1.203 |
| `ink_wash_painting` | vẽ tranh mực loang | 819 |
| `ukiyo-e` | tranh khắc gỗ ukiyo-e | 803 |
| `minimalism` | trường phái Tối giản | 597 |
| `impressionism` | trường phái Ấn tượng | 591 |
| `art_deco` | trường phái Art Deco | 372 |
| `renaissance` | phong cách phục hưng | 273 |
| `sumi-e` | tranh thuỷ mặc | 263 |
| `cubism` | trường phái Lập thể | 240 |
| `dunhuang_style` | phong cách tranh Đôn Hoàng | 181 |
| `memphis_design` | thiết kế Memphis | 128 |
| `greek_painting_style` | phong cách tranh Hy Lạp cổ | 127 |
| `pop_art` | nghệ thuật pop | 122 |
| `pointillism` | trường phái Điểm sắc | 95 |
| `expressionism` | trường phái Biểu hiện | 48 |

### 2.6 Phong cách thể loại (27 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `chibi` | chibi (vẽ đầu to người nhỏ) | 410.789 |
| `toony` | kiểu hoạt hình | 60.378 |
| `realistic` | thực tế | 39.195 |
| `style_parody` | nhái phong cách | 34.061 |
| `photo_(medium)` | ảnh chụp | 27.242 |
| `indian_style` | phong cách Ấn Độ | 21.361 |
| `official_style` | phong cách chính thức | 15.306 |
| `deformed` | biến dạng | 13.759 |
| `concept_art` | tranh ý tưởng | 10.700 |
| `novel_illustration` | minh hoạ tiểu thuyết | 9.461 |
| `photography_(artwork)` | ảnh chụp | 8.970 |
| `cover_art` | ảnh bìa | 6.848 |
| `toon_(style)` | phong cách toon (hoạt hình) | 5.999 |
| `style_emulation` | mô phỏng phong cách | 3.091 |
| `western_comics_(style)` | western comics (phong cách) | 2.506 |
| `photorealistic` | chân thực như ảnh | 1.807 |
| `anime_style` | phong cách anime | 883 |
| `pinup_(style)` | ảnh gợi cảm treo tường (phong cách) | 803 |
| `fleischer_style_toon` | hoạt hình kiểu Fleischer | 634 |
| `technical_illustration` | minh hoạ kỹ thuật | 439 |
| `manga_style` | phong cách manga | 310 |
| `semi-realistic` | bán thực tế | 187 |
| `retro_anime_style` | phong cách anime cổ điển | 182 |
| `rubber_hose_style` | phong cách ống nước cao su | 134 |
| `different_artstyle` | phong cách vẽ khác nhau | 129 |
| `alternate_art_style` | phong cách nghệ thuật khác | 99 |
| `moe` | phong cách moe | 34 |

### 2.7 Thời kỳ & thiết kế (11 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `retro_artstyle` | phong cách vẽ cổ điển | 24.810 |
| `2000s_(style)` | thập niên 2000 (phong cách) | 20.566 |
| `graffiti` | tranh phun sơn đường phố | 13.619 |
| `1990s_(style)` | thập niên 1990 (phong cách) | 13.254 |
| `1980s_(style)` | thập niên 1980 (phong cách) | 7.109 |
| `faux_retro_artstyle` | phong cách vẽ cổ điển giả | 4.231 |
| `y2k_(graphic_design)` | thiết kế đồ hoạ Y2K | 2.018 |
| `1970s_(style)` | 1970s (phong cách) | 1.236 |
| `synthwave` | phong cách synthwave | 1.017 |
| `vaporwave` | phong cách vaporwave | 607 |
| `1960s_(style)` | 1960s (phong cách) | 292 |

### 2.8 Nguồn & định dạng (dùng kèm) (4 tag)

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `comic` | truyện tranh | 1.161.974 |
| `official_art` | tranh chính thức | 561.608 |
| `4koma` | truyện tranh 4 khung | 119.230 |
| `yonkoma` | truyện 4 khung (yonkoma) | 39 |

### 2.9 Phong cách tác giả / series (229 tag)

*In 40 tag đầu theo số bài đăng; đủ 229 tag trong `style_tags.csv`.*

| Tag | Nghĩa | Bài đăng |
|---|---|---:|
| `alphes_(style)` | alphes (phong cách) | 16.123 |
| `zun_(style)` | zun (phong cách) | 1.962 |
| `araki_hirohiko_(style)` | araki hirohiko (phong cách) | 1.600 |
| `toriyama_akira_(style)` | toriyama akira (phong cách) | 1.405 |
| `puchimasu!_(style)` | puchimasu! (phong cách) | 1.393 |
| `riyo_(lyomsnpmp)_(style)` | riyo (lyomsnpmp) (phong cách) | 1.112 |
| `takeuchi_takashi_(style)` | takeuchi takashi (phong cách) | 921 |
| `sugimori_ken_(style)` | sugimori ken (phong cách) | 816 |
| `jikkyou_powerful_pro_yakyuu_(style)` | jikkyou powerful pro yakyuu (phong cách) | 783 |
| `bkub_(style)` | bkub (phong cách) | 781 |
| `pc-98_(style)` | pc-98 (phong cách) | 747 |
| `kubo_tite_(style)` | kubo tite (phong cách) | 645 |
| `panty_&_stocking_with_garterbelt_(style)` | panty & stocking with garterbelt (phong cách) | 632 |
| `minecraft_(style)` | minecraft (phong cách) | 623 |
| `vanripper_(style)` | vanripper (phong cách) | 568 |
| `komatsuzaki_rui_(style)` | komatsuzaki rui (phong cách) | 551 |
| `takenami_hideyuki_(style)` | takenami hideyuki (phong cách) | 510 |
| `ishikei_(style)` | ishikei (phong cách) | 507 |
| `fujiko_f_fujio_(style)` | fujiko f fujio (phong cách) | 473 |
| `watanabe_akio_(style)` | watanabe akio (phong cách) | 453 |
| `fukumoto_nobuyuki_(style)` | fukumoto nobuyuki (phong cách) | 420 |
| `itou_ikuko_(style)` | itou ikuko (phong cách) | 413 |
| `ohisashiburi_(style)` | ohisashiburi (phong cách) | 373 |
| `masanori_sato_(style)` | masanori sato (phong cách) | 364 |
| `omocat_(style)` | omocat (phong cách) | 361 |
| `gyari_(imagesdawn)_(style)` | gyari (imagesdawn) (phong cách) | 302 |
| `charles_schulz_(style)` | charles schulz (phong cách) | 289 |
| `aoki_ume_(style)` | aoki ume (phong cách) | 277 |
| `harukawa_moe_(style)` | harukawa moe (phong cách) | 264 |
| `bikkuriman_(style)` | bikkuriman (phong cách) | 255 |
| `fujimoto_tatsuki_(style)` | fujimoto tatsuki (phong cách) | 244 |
| `pokemon_rgby_(style)` | pokemon rgby (phong cách) | 234 |
| `walfie_(style)` | walfie (phong cách) | 233 |
| `channel_(caststation)_(style)` | channel (caststation) (phong cách) | 231 |
| `kantoku_(style)` | kantoku (phong cách) | 228 |
| `takemoto_izumi_(style)` | takemoto izumi (phong cách) | 210 |
| `nakayama_tooru_(style)` | nakayama tooru (phong cách) | 201 |
| `hara_tetsuo_(style)` | hara tetsuo (phong cách) | 197 |
| `oda_eiichirou_(style)` | oda eiichirou (phong cách) | 195 |
| `clamp_(circle)_(style)` | clamp (circle) (phong cách) | 189 |

---

## 3. Đã sửa những gì

Lần kiểm tra đầu phát hiện 41 tag phong cách **chưa có bản dịch** và 16 tag **dịch sai /
tối nghĩa**. Tất cả đã được sửa trong [`tools/dict/vi_style.py`](tools/dict/vi_style.py)
(từ điển này đứng đầu bảng ưu tiên nên thắng mọi từ điển cũ), rồi chạy lại
`python3 tools/build_vi.py`:

| Loại | Số tag | Ví dụ |
|---|---:|---|
| Thêm bản dịch mới | 41 | `art_nouveau` → trường phái Art Nouveau, `impressionism` → trường phái Ấn tượng, `rim_lighting` → ánh sáng viền, `low_poly`, `moe`, `webtoon`, `vaporwave`… |
| Sửa bản dịch sai hẳn | 3 | `lego` “chân” → **xếp hình Lego**; `spine_(medium)` “phần gáy sách” → **phần mềm Spine 2D**; `toon_(style)` “quá (phong cách)” → **phong cách toon (hoạt hình)** |
| Sửa bản dịch tối nghĩa | 13 | `surreal` “siêu thực mộng” → **siêu thực**; `spot_color` → **điểm xuyết màu**; `cel_rendering` → **render kiểu cel**; `brush_(medium)` → **cọ vẽ**; `felt_(medium)` → **vải nỉ**; `engraving_(medium)`, `etching_(artwork)`, `woodcut_(artwork)`, `simulated_traditional_(artwork)`, `digital_pastel_(artwork)`, `fudepen_(medium)`, `amigurumi_(medium)`, `multiple_monochrome` |
| Sửa luôn quy tắc “chất liệu X” | 13 | `opencanvas_(medium)`, `adobe_illustrator_(medium)`, `autodesk_sketchbook_(medium)`, `firealpaca_(medium)`, `art_academy_(medium)`, `dotpict_(medium)`, `blockbench_(medium)`, `airbrush_(medium)`, `acrylic_gouache_(medium)`, `embroidery_(medium)`, `ink_(artwork)`, `3d_(artwork)`, `tapestry_(medium)` |

Kết quả trong `danbooru_e621_vi_translation.csv`: **45.513 → 45.557 dòng** (thêm 44 dòng,
sửa 34 nghĩa). Độ phủ General Danbooru 97,59% → **97,60%**, General e621 97,09% → **97,10%**.
Các tag phái sinh cũng được hưởng theo: `psychedelic_background`, `art_deco_architecture`,
`semi-realistic_feral`, `abstract_colors`, `abstract_text`, `outrun_sun`.

### 3.1. Ba tag **không** đưa vào danh sách phong cách

`colorful_palette` (category 1 = Artist), `outrun` và `webtoon` (category 10 = Copyright) trùng
tên với tag phong cách nhưng thật ra là **tag tên nghệ sĩ / tên series** — nhóm tên riêng không
bao giờ được dịch (xem bảng category trong README). `tools/find_style_tags.py` tự lọc bỏ mọi
tag thuộc category 1/3/4/8/9/10/11, nên về sau thêm tag cũng không bị lẫn.

---

## 4. Sinh lại / kiểm tra

```bash
python3 tools/find_style_tags.py             # ghi lại style_tags.csv + in tóm tắt
python3 tools/find_style_tags.py --markdown  # in bảng Markdown như tài liệu này
python3 tools/find_style_tags.py --check     # kiểm tra mọi tag có thật trong danbooru_e621.csv
python3 colab/tests/test_style_tags.py       # hồi quy: CSV khớp lại được + không trùng tag
```

Muốn thêm một tag vào danh sách: thêm tên tag vào nhóm tương ứng trong `GROUPS` của
`tools/find_style_tags.py` rồi chạy `--check`. Script **báo lỗi nếu tag không tồn tại** trong
`danbooru_e621.csv`, nên không sợ gõ sai tên tag. Tag mới có đuôi `_(style)` thì tự động vào
nhóm "Phong cách tác giả / series", không cần khai báo.
