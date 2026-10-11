"""Tag "hệ thống" của họ Illustrious / NoobAI / WAI.

Những tag này KHÔNG có trong `danbooru_e621.csv` (vì chúng đến từ cột rating/score
của Danbooru và từ quy ước prompt của cộng đồng Illustrious, chứ không phải tag nội
dung), nhưng model họ Illustrious hiểu được. Vì vậy bộ dựng prompt phải tự cấp chúng.

Nguồn tham khảo đã kiểm chứng:
- Thẻ model WAI-illustrious-SDXL v17.0 (Civitai 827184, version 2883731):
  "There are four safety rating tags: general, sensitive, nsfw, explicit. Users are
  expected to consciously add 'nsfw' to negative prompts to filter inappropriate content."
  VAE tích hợp sẵn; Steps 15-30; CFG 5-7; Euler a; kích thước > 1024x1024;
  hires 1.5x + R-ESRGAN 4x+ Anime6B, denoising 0.35-0.5.
- Quy ước quality tag của NoobAI/Illustrious: masterpiece > best quality > high quality
  > normal > low > worst; tag thẩm mỹ "very awa" / "worst aesthetic".
"""

import json
import math
import os
from pathlib import Path


# ---------------------------------------------------------------- tag hệ thống
# tag -> (nghĩa tiếng Việt, nhóm)
# Nhóm dùng để xếp thứ tự prompt, xem groups.py
SYSTEM_TAGS = {
    # ---- phân loại nội dung (4 mức của thẻ model WAI) ----
    "rating_general":      ("phân loại: chung (an toàn)", "rating"),
    "rating_sensitive":    ("phân loại: nhạy cảm", "rating"),
    "rating_questionable": ("phân loại: đáng ngờ", "rating"),
    "rating_explicit":     ("phân loại: 18+ tường minh", "rating"),
    "rating_safe":         ("phân loại: an toàn (tên cũ Danbooru)", "rating"),
    "rating_nsfw":         ("phân loại: NSFW", "rating"),
    "nsfw":                ("nội dung người lớn", "rating"),
    "explicit":            ("cảnh 18+ tường minh", "rating"),
    "general":             ("nội dung phổ thông", "rating"),
    "sensitive":           ("nội dung nhạy cảm", "rating"),
    "questionable":        ("nội dung đáng ngờ", "rating"),

    # ---- chất lượng ----
    "masterpiece":         ("kiệt tác", "quality"),
    "best quality":        ("chất lượng tốt nhất", "quality"),
    "amazing quality":     ("chất lượng tuyệt vời", "quality"),
    "very good quality":   ("chất lượng rất tốt", "quality"),
    "high quality":        ("chất lượng cao", "quality"),
    "good quality":        ("chất lượng tốt", "quality"),
    "normal quality":      ("chất lượng bình thường", "quality"),
    "low quality":         ("chất lượng thấp", "quality"),
    "bad quality":         ("chất lượng kém", "quality"),
    "worst quality":       ("chất lượng tệ nhất", "quality"),
    "newest":              ("nét vẽ đời mới", "quality"),
    "highres":             ("độ phân giải cao", "quality"),
    "absurdres":           ("độ phân giải cực cao", "quality"),
    "very awa":            ("thẩm mỹ rất cao (tag riêng của NoobAI)", "quality"),
    "worst aesthetic":     ("thẩm mỹ tệ nhất", "quality"),
    "award-winning":       ("đạt giải thưởng", "quality"),
    "hyper-detailed":      ("siêu chi tiết", "quality"),
    "highly detailed":     ("rất chi tiết", "quality"),
    "intricate details":   ("chi tiết cầu kỳ", "quality"),
    "sharp focus":         ("lấy nét sắc", "quality"),
    "8k uhd":              ("8K siêu nét", "quality"),
    "professional":        ("chuyên nghiệp", "quality"),

    # ---- nguồn / phong cách gốc ----
    "source_anime":        ("nguồn: anime", "source"),
    "source_cartoon":      ("nguồn: hoạt hình phương Tây", "source"),
    "source_furry":        ("nguồn: furry", "source"),
    "source_pony":         ("nguồn: My Little Pony", "source"),
    "source_game":         ("nguồn: trò chơi", "source"),
    "source_vn":           ("nguồn: visual novel", "source"),
    "anime style":         ("phong cách anime", "source"),
    "vibrant colors":      ("màu sắc rực rỡ", "source"),
    "cel shading":         ("đổ bóng kiểu anime", "source"),
    "flat color":          ("màu phẳng", "source"),
    "thick lineart":       ("nét viền dày", "source"),
    "no lineart":          ("không có nét viền", "source"),
    "film grain":          ("hạt phim", "source"),
    "ambient occlusion":   ("đổ bóng tiếp xúc", "source"),
    "raytracing":          ("dò tia sáng", "source"),

    # ---- niên đại (NoobAI hỗ trợ tag năm sáng tác) ----
    "early":               ("thời kỳ đầu", "source"),
    "old":                 ("nét vẽ cũ", "source"),
    "recent":              ("gần đây", "source"),

    # ---- negative phổ biến không có trong danh sách tag ----
    "sketch":              ("phác thảo", "negative"),
    "censor":              ("bị kiểm duyệt", "negative"),
    "censored":            ("đã kiểm duyệt", "negative"),
    "uncensored":          ("không kiểm duyệt", "negative"),
    "jpeg artifacts":      ("nhiễu nén jpeg", "negative"),
    "bad anatomy":         ("giải phẫu sai", "negative"),
    "bad hands":           ("bàn tay lỗi", "negative"),
    "bad proportions":     ("tỷ lệ cơ thể sai", "negative"),
    "extra digits":        ("thừa ngón", "negative"),
    "fewer digits":        ("thiếu ngón", "negative"),
    "extra limbs":         ("thừa tay chân", "negative"),
    "missing limbs":       ("thiếu tay chân", "negative"),
    "fused fingers":       ("ngón tay dính nhau", "negative"),
    "malformed hands":     ("bàn tay dị dạng", "negative"),
    "long neck":           ("cổ dài bất thường", "negative"),
    "deformed":            ("biến dạng", "negative"),
    "disfigured":          ("méo mó", "negative"),
    "ugly":                ("xấu", "negative"),
    "blurry":              ("mờ nhoè", "negative"),
    "greyscale":           ("trắng đen", "negative"),
    "monochrome":          ("đơn sắc", "negative"),
    "watermark":           ("chữ chìm", "negative"),
    "text":                ("chữ", "negative"),
    "signature":           ("chữ ký", "negative"),
    "username":            ("tên người dùng", "negative"),
    "artist name":         ("tên hoạ sĩ", "negative"),
    "copyright name":      ("tên bản quyền", "negative"),
    "worst detail":        ("chi tiết tệ nhất", "negative"),
    "multiple views":      ("nhiều góc nhìn trong một ảnh", "negative"),
    "mutated":             ("dị tật", "negative"),
}

# Các tag hệ thống nên được đề xuất khi gõ trong tagcomplete
# (những tag đã có sẵn trong danbooru_e621.csv sẽ được lọc ra khi sinh file)
SYSTEM_TAG_CATEGORIES = {
    "rating": 5,     # Meta (Danbooru)
    "quality": 5,
    "source": 5,
    "negative": 0,   # General
}


# ---------------------------------------------------------------- preset chất lượng
QUALITY_PRESETS = {
    "WAI khuyến nghị (đầy đủ)": "masterpiece, best quality, amazing quality, newest, highres, absurdres",
    "NoobAI thẩm mỹ cao": "very awa, masterpiece, best quality, newest, highres, absurdres",
    "Ngắn gọn": "masterpiece, best quality, highres",
    "Không dùng tag chất lượng": "",
}

# ---------------------------------------------------------------- preset negative
NEGATIVE_PRESETS = {
    "WAI khuyến nghị (ngắn)": "bad quality, worst quality, worst detail, sketch, censor",
    "Chuẩn cộng đồng (đầy đủ)": (
        "lowres, worst quality, bad quality, normal quality, sketch, censor, "
        "jpeg artifacts, bad anatomy, bad hands, bad proportions, extra digits, fewer digits, "
        "extra limbs, missing limbs, fused fingers, malformed hands, long neck, deformed, "
        "disfigured, ugly, blurry, watermark, text, signature, username, artist name"
    ),
    "Ngắn": "lowres, bad anatomy, bad hands, watermark, signature",
    "Không dùng negative": "",
}

# ---------------------------------------------------------------- mức phân loại
# Thẻ model WAI v17 liệt kê 4 mức: general / sensitive / nsfw / explicit.
# Cộng đồng Illustrious cũng dùng dạng rating_* theo chuẩn Danbooru/e621, nên ở đây
# ta đưa cả hai biến thể vào negative để chắc chắn model lọc đúng.
RATINGS = [
    {
        "id": "general",
        "label": "An toàn — general",
        "positive": ["rating_general", "general"],
        "negative": ["rating_sensitive", "rating_questionable", "rating_explicit",
                     "sensitive", "nsfw", "explicit"],
    },
    {
        "id": "sensitive",
        "label": "Nhạy cảm — sensitive (hở nhẹ, không 18+)",
        "positive": ["rating_sensitive", "sensitive"],
        "negative": ["rating_questionable", "rating_explicit", "nsfw", "explicit"],
    },
    {
        "id": "questionable",
        "label": "Đáng ngờ — questionable",
        "positive": ["rating_questionable", "questionable"],
        "negative": ["rating_general", "general"],
    },
    {
        "id": "explicit",
        "label": "18+ — explicit (bỏ 'nsfw' khỏi negative)",
        "positive": ["rating_explicit", "explicit"],
        "negative": ["rating_general", "general", "censor", "censored"],
    },
]


# ---------------------------------------------------------------- tham số WAI v17
# Đúng theo thẻ model: Steps 15-30, CFG 5-7, Euler a, >1024x1024, VAE đã tích hợp,
# hires fix 1.5x với R-ESRGAN 4x+ Anime6B và denoising 0.35-0.5.
WAI_DEFAULTS = {
    "steps": 25,
    "cfg_scale": 6.0,
    "sampler_name": "Euler a",
    "scheduler": "",            # để mặc định của Forge
    "clip_skip": 2,
    "width": 1024,
    "height": 1344,
    "seed": -1,
    "batch_size": 1,
    "enable_hr": True,
    "hr_upscaler": "RealESRGAN_x4plus_anime_6B",
    "hr_scale": 1.5,
    "hr_second_pass_steps": 20,
    "denoising_strength": 0.4,
}

# --------------------------------------------------------------------- profile
# Tham số khuyến nghị THEO BIẾN THỂ model — khớp với catalog trong colab/install.sh.
# Bản HSWQ turbo là merge tăng tốc (DMD2) nên CFG/steps khác hẳn bản FP16: dùng
# CFG 6 với nó sẽ cháy ảnh. colab/install.sh export WAI_PROFILE_* lúc cài, nhờ vậy
# chọn `--model hswq` thì bộ dựng prompt tự đổi tham số, không phải sửa tay.
MODEL_PROFILES = {
    "fp16": {
        "label": "WAI-illustrious-SDXL v17.0 FP16 (bản gốc của WAI0731)",
        "steps": 25, "cfg_scale": 6.0, "sampler_name": "Euler a", "clip_skip": 2,
        "hr_second_pass_steps": 20,
    },
    "fp8": {
        "label": "WAI v17.0 FP8 e4m3 (lượng tử hoá, nhẹ VRAM)",
        "steps": 25, "cfg_scale": 6.5, "sampler_name": "Euler a", "clip_skip": 2,
        "hr_second_pass_steps": 20,
    },
    "int8": {
        "label": "WAI v17.0 INT8 convrot (lượng tử hoá 8-bit)",
        "steps": 25, "cfg_scale": 6.5, "sampler_name": "Euler a", "clip_skip": 2,
        "hr_second_pass_steps": 20,
    },
    "hswq": {
        "label": "WAI v17.0 HSWQ turbo r32 (DMD2 — sinh nhanh)",
        "steps": 10, "cfg_scale": 1.0, "sampler_name": "Euler a", "clip_skip": 2,
        "hr_second_pass_steps": 10,
    },
}
DEFAULT_PROFILE_ID = "fp16"

# Các khoá được phép ghi vào WAI_DEFAULTS. Cố ý hẹp: KHÔNG cho thêm khoá lạ vào
# dict này vì builder.payload() gửi nguyên dict đó lên /sdapi/v1/txt2img.
_PROFILE_KEYS = ("steps", "cfg_scale", "sampler_name", "clip_skip", "hr_second_pass_steps")
_ENV_CAST = {
    "WAI_PROFILE_CFG": ("cfg_scale", float),
    "WAI_PROFILE_STEPS": ("steps", int),
    "WAI_PROFILE_SAMPLER": ("sampler_name", str),
}


def apply_model_profile(defaults=None, env=None):
    """Ghi tham số của biến thể model đang cài vào dict mặc định (sửa tại chỗ).

    Nguồn ưu tiên: biến môi trường lẻ (WAI_PROFILE_CFG/STEPS/SAMPLER) > catalog
    MODEL_PROFILES theo WAI_PROFILE_MODEL_ID > giữ nguyên giá trị sẵn có.

    Trả về ``(profile_id, {khoá: giá trị đã ghi})``; profile_id là "" nếu môi trường
    không khai báo biến thể nào (khi đó mặc định fp16 được giữ nguyên).
    """
    env = dict(os.environ) if env is None else dict(env)
    target = WAI_DEFAULTS if defaults is None else defaults
    mid = (env.get("WAI_PROFILE_MODEL_ID") or "").strip().lower()
    prof = MODEL_PROFILES.get(mid)
    applied = {}
    if prof:
        for key in _PROFILE_KEYS:
            if key in prof:
                applied[key] = prof[key]
    for env_key, (key, cast) in _ENV_CAST.items():
        raw = (env.get(env_key) or "").strip()
        if not raw:
            continue
        try:
            value = cast(raw)
            if key == "cfg_scale" and (not math.isfinite(value) or not 0 <= value <= 30):
                continue
            if key == "steps" and not 1 <= value <= 200:
                continue
            applied[key] = value
        except (ValueError, TypeError):
            continue
    if applied:
        target.update(applied)
    return (mid if prof else ""), applied


def profile_environment():
    """Đọc profile JSON do bộ cài lưu; biến môi trường lần này luôn được ưu tiên.

    Chỉ đọc dữ liệu, không source/eval file. App độc lập không phải kế thừa
    environment của tiến trình Bash đã cài model.
    """
    env = {}
    path = Path(os.environ.get("WAI_PROFILE_FILE") or
                Path(__file__).resolve().parents[1] / "assets" / "model_profile.json")
    keys = {"WAI_PROFILE_MODEL_ID", *_ENV_CAST}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            env.update({k: str(v) for k, v in data.items() if k in keys and isinstance(v, (str, int, float))})
    except (OSError, ValueError):
        pass
    env.update({k: v for k, v in os.environ.items() if k in keys})
    return env


ACTIVE_PROFILE_ID, ACTIVE_PROFILE_OVERRIDES = apply_model_profile(env=profile_environment())

# Kích thước chuẩn của SDXL/Illustrious (model yêu cầu > 1024x1024)
SIZE_PRESETS = {
    "Chân dung 1024×1344 (khuyến nghị)": (1024, 1344),
    "Vuông 1024×1024": (1024, 1024),
    "Ngang 1344×1024": (1344, 1024),
    "Dọc dài 896×1152": (896, 1152),
    "Ngang dài 1152×896": (1152, 896),
    "Dọc cao 832×1216": (832, 1216),
    "Ngang rộng 1216×832": (1216, 832),
    "Rạp 1536×640": (1536, 640),
    "Vuông lớn 1536×1536 (hires sẵn)": (1536, 1536),
}

# Upscaler phù hợp cho nét anime.
# LƯU Ý: Forge Neo KHÔNG có sẵn scaler tên "R-ESRGAN 4x+ Anime6B". Lớp UpscalerESRGAN
# của nó quét thư mục models/ESRGAN và đặt tên scaler THEO TÊN FILE
# (modules/modelloader.py: friendly_name() trả về basename không đổi phần mở rộng),
# nên RealESRGAN_x4plus_anime_6B.pth hiện ra đúng là "RealESRGAN_x4plus_anime_6B".
# A1111/Forge classic lại dùng tên "R-ESRGAN 4x+ Anime6B". Ta kê cả hai và chọn động.
UPSCALERS = [
    "RealESRGAN_x4plus_anime_6B",   # Forge Neo (theo tên file)
    "R-ESRGAN 4x+ Anime6B",         # A1111 / Forge classic
    "RealESRGAN_x4plus",
    "R-ESRGAN 4x+",
    "ESRGAN_4x",
    "SwinIR_4x",
    "LDSR",
    "Latent",
]


def pick_upscaler(available, prefer=WAI_DEFAULTS["hr_upscaler"]):
    """Chọn upscaler anime tốt nhất trong danh sách mà backend THỰC SỰ có.

    Nhận danh sách từ GET /sdapi/v1/upscalers. Nếu backend không có bản anime 6B thì
    lùi dần sang R-ESRGAN thường -> bất kỳ ESRGAN nào -> cái đầu tiên không phải Latent,
    để payload không bao giờ trỏ tới một upscaler không tồn tại.
    """
    if not available:
        return prefer
    if prefer in available:
        return prefer

    def flat(name):
        return name.lower().replace(" ", "_").replace("-", "_")

    ranked = sorted(available, key=flat)
    # tên file của Real-ESRGAN là "x4plus" (x đứng trước 4), còn A1111 lại đặt tên
    # scaler là "4x+" -> phải dò cả hai trật tự.
    for needle in (("anime", "6b"), ("anime",), ("esrgan", "x4"), ("esrgan", "4x"),
                   ("esrgan",)):
        for name in ranked:
            flat_name = flat(name)
            if all(part in flat_name for part in needle):
                return name
    for name in ranked:
        if flat(name) not in ("none", "latent"):
            return name
    return ranked[0]
