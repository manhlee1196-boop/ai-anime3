# -*- coding: utf-8 -*-
"""Bản dịch cho nhóm tag **phong cách vẽ** (chất liệu, kỹ thuật, trường phái, ánh sáng).

Bổ sung ba loại:
1. Tag phong cách chưa có bản dịch trong kho (41 tag) — trước đây không tra được
   bằng tiếng Việt trong tab "Prompt VN".
2. Tag có bản dịch sai hẳn: `lego` ("chân"), `spine_(medium)` ("phần gáy sách"),
   `toon_(style)` ("quá (phong cách)").
3. Tag có bản dịch tối nghĩa do quy tắc `X_(medium)` → "chất liệu X": giữ nguyên tên
   phần mềm tiếng Anh, hoặc đọc lên không rõ nghĩa.

Từ điển này được ưu tiên cao nhất trong `tools/build_vi.py`, nên sửa ở đây sẽ thắng
mọi từ điển khác. Chạy lại `python3 tools/build_vi.py` sau khi thêm dòng mới.
"""

VI_STYLE = {
    # ---------------------------------------------------------------- chất liệu in/thủ công
    "woodcut_(artwork)": "tranh khắc gỗ",
    "engraving_(medium)": "tranh khắc (engraving)",
    "etching_(artwork)": "tranh khắc axit (etching)",
    "tapestry": "thảm dệt treo tường",
    "kirigami": "nghệ thuật cắt giấy (kirigami)",
    "felt_(medium)": "vải nỉ",
    "amigurumi_(medium)": "thú bông móc len",
    "brush_(medium)": "cọ vẽ",
    "airbrush_(medium)": "vẽ bằng cọ phun (airbrush)",
    "fudepen_(medium)": "bút lông nước Nhật (fudepen)",
    "acrylic_gouache_(medium)": "màu acrylic gouache",
    "digital_pastel_(artwork)": "phấn tiên kỹ thuật số",
    "simulated_traditional_(artwork)": "giả chất liệu truyền thống",
    "embroidery_(medium)": "tranh thêu",
    "ink_(artwork)": "tranh vẽ bằng mực",
    "lego": "xếp hình Lego",

    # ---------------------------------------------------------------- chất liệu số & CG
    "3d_(artwork)": "tác phẩm 3D",
    "low_poly": "đồ hoạ đa giác thấp (low-poly)",
    "voxel_art": "nghệ thuật khối voxel",
    "spine_(medium)": "phần mềm Spine 2D",
    "opencanvas_(medium)": "vẽ bằng OpenCanvas",
    "adobe_illustrator_(medium)": "vẽ bằng Adobe Illustrator",
    "autodesk_sketchbook_(medium)": "vẽ bằng Autodesk Sketchbook",
    "firealpaca_(medium)": "vẽ bằng FireAlpaca",
    "art_academy_(medium)": "vẽ bằng Art Academy",
    "dotpict_(medium)": "vẽ bằng Dotpict",
    "blockbench_(medium)": "vẽ bằng Blockbench",

    # ---------------------------------------------------------------- kỹ thuật hoàn thiện
    "painterly": "nét vẽ kiểu hội hoạ",
    "impasto": "kỹ thuật sơn dày (impasto)",
    "chiaroscuro": "tương phản sáng tối mạnh (chiaroscuro)",
    "linear_hatching": "đánh bóng bằng nét thẳng song song",
    "complex_shading": "đổ bóng phức tạp",
    "minimal_shading": "đổ bóng tối giản",
    "cel_rendering": "render kiểu cel",
    "spot_color": "điểm xuyết màu",
    "multiple_monochrome": "nhiều hình đơn sắc",
    "colorful_palette": "bảng màu rực rỡ",
    "dithering": "kỹ thuật chấm pha điểm ảnh",
    "halftone": "chấm tram (halftone)",
    "screentone": "chấm tram truyện tranh (screentone)",
    "screentones": "chấm tram truyện tranh (screentones)",
    "stippling": "chấm điểm tạo bóng",

    # ---------------------------------------------------------------- ánh sáng
    "sidelighting": "ánh sáng chiếu ngang",
    "underlighting": "ánh sáng chiếu từ dưới",
    "dramatic_lighting": "ánh sáng kịch tính",
    "mood_lighting": "ánh sáng theo tâm trạng",
    "rim_lighting": "ánh sáng viền",

    # ---------------------------------------------------------------- trường phái & mỹ thuật
    "abstract": "trừu tượng",
    "art_nouveau": "trường phái Art Nouveau",
    "art_deco": "trường phái Art Deco",
    "psychedelic": "phong cách ảo giác",
    "nihonga": "tranh Nhật hiện đại (nihonga)",
    "surreal": "siêu thực",
    "surrealism": "trường phái Siêu thực",
    "minimalism": "trường phái Tối giản",
    "impressionism": "trường phái Ấn tượng",
    "cubism": "trường phái Lập thể",
    "expressionism": "trường phái Biểu hiện",
    "pointillism": "trường phái Điểm sắc",
    "dunhuang_style": "phong cách tranh Đôn Hoàng",
    "greek_painting_style": "phong cách tranh Hy Lạp cổ",
    "memphis_design": "thiết kế Memphis",

    # ---------------------------------------------------------------- phong cách thể loại
    "toon_(style)": "phong cách toon (hoạt hình)",
    "moe": "phong cách moe",
    "semi-realistic": "bán thực tế",
    "style_emulation": "mô phỏng phong cách",
    "fleischer_style_toon": "hoạt hình kiểu Fleischer",

    # ---------------------------------------------------------------- nguồn & định dạng
    "webtoon": "truyện tranh mạng (webtoon)",
    "yonkoma": "truyện 4 khung (yonkoma)",

    # ---------------------------------------------------------------- thời kỳ & thiết kế
    "faux_retro_artstyle": "phong cách vẽ cổ điển giả",
    "y2k_(graphic_design)": "thiết kế đồ hoạ Y2K",
    "vaporwave": "phong cách vaporwave",
    "synthwave": "phong cách synthwave",
    "outrun": "phong cách outrun",
}
