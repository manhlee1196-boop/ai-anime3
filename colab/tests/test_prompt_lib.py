"""Kiểm tra hồi quy cho prompt_lib.

Chạy:  python3 colab/tests/test_prompt_lib.py      (từ thư mục gốc repo)
Bộ kiểm tra chạy độc lập bằng Python, không cần pytest.
"""

import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "colab"))

from prompt_lib import (GROUP_LABELS, MODEL_PROFILES, WAI_DEFAULTS, PromptBuilder,  # noqa: E402
                        TagIndex, apply_model_profile, find_repo_root, get_index,
                        norm, parse_pieces, unaccent)

FAILS = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILS.append(f"{label}: nhận {got!r}, mong {want!r}")
    print(f"  {'✓' if ok else '✗'} {label:<46} {got if ok else f'{got!r} != {want!r}'}")
    return ok


def check_in(label, needle, haystack):
    ok = needle in haystack
    if not ok:
        FAILS.append(f"{label}: thiếu {needle!r} trong {haystack!r}")
    print(f"  {'✓' if ok else '✗'} {label:<46} {needle if ok else f'thiếu {needle} trong {haystack}'}")
    return ok


def main():
    root = find_repo_root(HERE) or ROOT
    print(f"Thư mục kho prompt: {root}\n")
    index = TagIndex(root)
    stats = index.stats()
    print("1) Nạp mục lục")
    assert stats["tổng_số_tag"] > 300_000, stats
    assert stats["có_nghĩa_tiếng_việt"] > 40_000, stats
    print(f"  ✓ {stats['tổng_số_tag']:,} tag, {stats['có_nghĩa_tiếng_việt']:,} có nghĩa tiếng Việt, "
          f"{stats['tag_hệ_thống']} tag hệ thống, {stats['bí_danh']:,} bí danh\n")

    print("2) Bỏ dấu tiếng Việt")
    check("unaccent('Áo dài trắng')", unaccent("Áo dài trắng"), "Ao dai trang")
    check("norm('Trường_Học')", norm("Trường_Học"), "truong hoc")

    print("\n3) Tra tiếng Việt -> tag tiếng Anh (top 1)")
    for query, want in [
        ("tóc dài", "long_hair"),
        ("đồng phục học sinh", "school_uniform"),
        ("mắt đỏ", "red_eyes"),
        ("cầm kiếm", "holding_sword"),
        ("hoa anh đào", "cherry_blossoms"),
        ("kền kền Ai Cập", "egyptian_vulture"),
        ("nhìn vào người xem", "looking_at_viewer"),
    ]:
        hits = index.search(query, limit=1)
        check(f"'{query}'", hits[0].tag if hits else "(không có)", want)

    print("\n4) Tra không cần gõ dấu")
    for query, want in [("ao dai", "ao_dai"), ("toc dai", "long_hair"),
                        ("mat do", "red_eyes")]:
        hits = index.search(query, limit=1)
        check(f"'{query}'", hits[0].tag if hits else "(không có)", want)

    print("\n5) Khớp đủ mọi từ, không cần đúng thứ tự")
    hits = index.search("nhìn người xem", limit=5)
    check_in("'nhìn người xem' phải ra looking_at_viewer", "looking_at_viewer",
             [h.tag for h in hits])

    print("\n6) Từ có dấu không bị lẫn với từ gần âm")
    hits = index.search("váy", limit=1)
    check("'váy' (không phải 'vảy'/'vây')", hits[0].tag if hits else "(không có)", "skirt")

    print("\n7) Tra tag hệ thống Illustrious/WAI")
    for tag in ("masterpiece", "rating_explicit", "rating_general", "very awa", "newest"):
        check_in(f"'{tag}'", tag, [h.tag for h in index.search(tag, limit=5)])
    check("nghĩa của masterpiece", index.vi_of("masterpiece"), "kiệt tác")

    print("\n8) Phân nhóm tag")
    cases = {
        "1girl": "Số lượng", "long_hair": "Ngoại hình", "red_eyes": "Ngoại hình",
        "white_shirt": "Trang phục", "black_dress": "Trang phục", "ao_dai": "Trang phục",
        "bikini": "Trang phục", "ribbon": "Trang phục", "smiling": "Biểu cảm",
        "tongue_out": "Biểu cảm", "sitting": "Tư thế", "on_back": "Tư thế",
        "hand_on_head": "Tư thế", "holding_sword": "Hành động", "sword": "Đạo cụ",
        "katana": "Đạo cụ", "flowers": "Bối cảnh", "cherry_blossoms": "Bối cảnh",
        "from_behind": "Góc máy", "close-up": "Góc máy", "male_focus": "Góc máy",
        "dragon": "Loài", "anthro": "Loài", "dragon_tail": "Ngoại hình",
        "fox_ears": "Ngoại hình", "genitals": "18+", "ejaculation": "18+",
        "breasts": "Ngoại hình", "big_breasts": "Ngoại hình", "presenting": "18+",
        "english_text": "Meta", "speech_bubble": "Meta", "border": "Meta",
        "2024": "Nguồn", "chibi": "Nguồn", "furniture": "Bối cảnh", "fur": "Ngoại hình",
        "artist:wlop": "Hoạ sĩ", "loli": "Số lượng", "robot": "Loài",
    }
    for tag, want in cases.items():
        got = GROUP_LABELS.get(index.group_of(tag), index.group_of(tag))
        check(f"{tag}", got.startswith(want), True)

    print("\n9) Ghép prompt: thứ tự nhóm + khử trùng lặp + trọng số")
    builder = PromptBuilder(index)
    out = builder.assemble(
        "1girl, long_hair, red_eyes, school_uniform, holding_sword, cherry_blossoms, "
        "from_behind, (large_breasts:1.1), 1girl, hatsune_miku",
        description="Một cô gái đứng dưới cơn mưa hoa anh đào",
        rating_id="general", quality_preset="WAI khuyến nghị (đầy đủ)")
    prompt = out["prompt"]
    print(f"  PROMPT: {prompt}")
    # câu mô tả đi đầu
    check("mô tả đứng đầu", prompt.startswith("Một cô gái đứng dưới cơn mưa hoa anh đào"), True)
    # chất lượng trước tag nội dung
    check("masterpiece trước 1girl",
          prompt.index("masterpiece") < prompt.index("1girl"), True)
    # phân loại đứng ngay sau chất lượng
    check("rating_general trước chủ thể",
          prompt.index("rating_general") < prompt.index("1girl"), True)
    # không lặp tag
    check("1girl không bị lặp", prompt.count("1girl"), 1)
    # trọng số giữ nguyên
    check_in("giữ trọng số", "(large_breasts:1.1)", prompt)
    # ngoại hình trước trang phục, trang phục trước hành động
    check("long_hair trước school_uniform",
          prompt.index("long_hair") < prompt.index("school_uniform"), True)
    check("school_uniform trước holding_sword",
          prompt.index("school_uniform") < prompt.index("holding_sword"), True)
    # bối cảnh sau hành động
    check("holding_sword trước cherry_blossoms",
          prompt.index("holding_sword") < prompt.index("cherry_blossoms"), True)

    print("\n10) Negative tự chứa các mức phân loại không chọn")
    neg = builder.negative("general", "Chuẩn cộng đồng (đầy đủ)")
    for token in ("lowres", "bad anatomy", "bad hands", "rating_explicit", "nsfw"):
        check_in("negative 'general'", token, neg)
    neg18 = builder.negative("explicit", "WAI khuyến nghị (ngắn)")
    check("'explicit' không tự chặn chính nó", "rating_explicit" in neg18, False)
    check_in("'explicit' chặn mức an toàn", "rating_general", neg18)

    print("\n11) Không nhầm cú pháp trọng số với tag có dấu hai chấm")
    pieces, specials, unresolved = parse_pieces(
        "16:9, :3, 9/11, (solo:1.2), <lora:abc:0.8>, áo dài", index)
    tags = [t for t, _ in pieces]
    check_in("16:9 giữ nguyên", "16:9", tags)
    check_in(":3 giữ nguyên", ":3", tags)
    check_in("9/11 giữ nguyên", "9/11", tags)
    check_in("trọng số được tách", "solo", tags)
    check_in("lora đưa vào nhóm riêng", "<lora:abc:0.8>", [t for t, _ in specials])
    check_in("tiếng Việt tự tra ngược thành tag", "ao_dai", tags)

    print("\n12) Payload cho API Forge")
    payload = builder.payload(prompt, neg, {"width": 832, "height": 1216, "steps": 28})
    check("sampler", payload["sampler_name"], "Euler a")
    check("steps", payload["steps"], 28)
    check("cfg trong khoảng thẻ model khuyên (5-7)", 5 <= payload["cfg_scale"] <= 7, True)
    check("kích thước", (payload["width"], payload["height"]), (832, 1216))
    check("upscaler hires = mặc định WAI", payload["hr_upscaler"],
          WAI_DEFAULTS["hr_upscaler"])
    # Forge Neo đặt tên scaler theo tên file, A1111 dùng tên khác -> phải tự dò
    check("tự chọn upscaler kiểu Forge Neo",
          PromptBuilder.fix_upscaler(dict(payload, enable_hr=True),
                                     ["Latent", "RealESRGAN_x4plus_anime_6B", "ESRGAN"]
                                     )["hr_upscaler"],
          "RealESRGAN_x4plus_anime_6B")
    check("tự chọn upscaler kiểu A1111",
          PromptBuilder.fix_upscaler(dict(payload, enable_hr=True),
                                     ["Latent", "R-ESRGAN 4x+ Anime6B", "LDSR"]
                                     )["hr_upscaler"],
          "R-ESRGAN 4x+ Anime6B")
    check("lùi sang bản x4 thường khi thiếu bản anime",
          PromptBuilder.fix_upscaler(dict(payload, enable_hr=True),
                                     ["Latent", "RealESRGAN_x4plus", "ESRGAN"]
                                     )["hr_upscaler"],
          "RealESRGAN_x4plus")
    check("có prompt", payload["prompt"] == prompt, True)

    print("\n13) Duyệt thư viện theo nhóm + tag ngẫu nhiên")
    for group in ("clothing", "appearance", "background", "sexual"):
        rows = index.top_in_group(group, limit=5, min_count=20_000)
        assert rows, f"nhóm {group} rỗng"
        print(f"  ✓ {GROUP_LABELS[group]:<26} ví dụ: {', '.join(r.tag for r in rows[:3])}")
    rnd = index.random_tags(8, seed=42)
    check("random_tags trả đủ 8 tag", len(rnd), 8)
    check("random ổn định theo seed",
          [r.tag for r in index.random_tags(8, seed=42)], [r.tag for r in rnd])
    sfw = index.random_tags(40, seed=1)
    check("random SFW không có tag 18+",
          any(r.group == "sexual" for r in sfw), False)
    check("random SFW chỉ lấy tag Danbooru (cat 0/5)",
          all(r.category in (0, 5) for r in sfw), True)
    wide = index.random_tags(200, seed=1, allow_nsfw=True)
    check("bật allow_nsfw thì có tag 18+ và cả e621",
          any(r.group == "sexual" for r in wide), True)
    check("bật allow_nsfw thì có tag e621 (cat 7/12)",
          any(r.category in (7, 12) for r in wide), True)

    print("\n14) styles.csv cho Forge")
    csv_text = builder.styles_csv()
    check("4 mức phân loại + 12 công thức phong cách", csv_text.count("\n"), 17)
    check_in("dòng đầu là header", "name,prompt,negative_prompt", csv_text)
    check_in("có Style phong cách bấm được", "Phong cách — Tranh màu nước", csv_text)
    sketch_row = [r for r in csv.reader(io.StringIO(csv_text))
                  if r[0] == "Phong cách — Phác thảo chì"][0]
    check("negative của Style 'Phác thảo chì' không chứa sketch", 
          "sketch" in sketch_row[2].split(", "), False)

    print("\n15) Biến thể model (profile do colab/install.sh chọn)")
    check("có đủ 4 biến thể trong catalog", sorted(MODEL_PROFILES), ["fp16", "fp8", "hswq", "int8"])
    d = dict(WAI_DEFAULTS)
    mid, applied = apply_model_profile(d, {"WAI_PROFILE_MODEL_ID": "hswq"})
    check("chọn hswq → trả đúng id", mid, "hswq")
    check("hswq đổi CFG về 1.0 (bản turbo, CFG 6 sẽ cháy ảnh)", d["cfg_scale"], 1.0)
    check("hswq đổi steps về 10", d["steps"], 10)
    check("hswq đổi steps của lượt hires", d["hr_second_pass_steps"], 10)
    check("hswq có ghi khoá vào dict", "cfg_scale" in applied and "steps" in applied, True)
    d = dict(WAI_DEFAULTS)
    apply_model_profile(d, {"WAI_PROFILE_MODEL_ID": "fp8"})
    check("fp8 dùng CFG 6.5 theo thẻ model lượng tử hoá", d["cfg_scale"], 6.5)
    d = dict(WAI_DEFAULTS)
    apply_model_profile(d, {"WAI_PROFILE_MODEL_ID": "fp16"})
    check("fp16 giữ tham số gốc của thẻ model", (d["cfg_scale"], d["steps"]), (6.0, 25))
    d = dict(WAI_DEFAULTS)
    apply_model_profile(d, {"WAI_PROFILE_MODEL_ID": "hswq", "WAI_PROFILE_CFG": "2.5",
                            "WAI_PROFILE_STEPS": "15"})
    check("biến môi trường lẻ thắng catalog (để tinh chỉnh tay)", (d["cfg_scale"], d["steps"]), (2.5, 15))
    d = dict(WAI_DEFAULTS)
    mid, applied = apply_model_profile(d, {"WAI_PROFILE_MODEL_ID": "gguf"})
    check("id lạ → không đổi gì, trả id rỗng", (mid, applied, d["cfg_scale"]), ("", {}, 6.0))
    d = dict(WAI_DEFAULTS)
    apply_model_profile(d, {"WAI_PROFILE_CFG": "không-phải-số"})
    check("giá trị rác không gây nổ, giữ mặc định", d["cfg_scale"], 6.0)
    d = dict(WAI_DEFAULTS)
    apply_model_profile(d, {})
    check("không có env → giữ mặc định fp16", d["cfg_scale"], 6.0)
    # WAI_DEFAULTS được gửi NGUYÊN KHỐI lên /sdapi/v1/txt2img nên cấm thêm khoá lạ
    check("apply_model_profile không làm bẩn WAI_DEFAULTS toàn cục",
          set(WAI_DEFAULTS) <= {"steps", "cfg_scale", "sampler_name", "scheduler", "clip_skip",
                                "width", "height", "seed", "batch_size", "enable_hr",
                                "hr_upscaler", "hr_scale", "hr_second_pass_steps",
                                "denoising_strength"}, True)
    check("payload không chứa khoá ngoài API",
          set(builder.payload(prompt, neg)) - {"prompt", "negative_prompt", "override_settings", "override_settings_restore_afterwards"} <= set(WAI_DEFAULTS), True)

    print("\n" + "=" * 68)
    if FAILS:
        print(f"THẤT BẠI: {len(FAILS)} kiểm tra")
        for f in FAILS:
            print("  -", f)
        return 1
    print("TẤT CẢ KIỂM TRA ĐỀU ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
