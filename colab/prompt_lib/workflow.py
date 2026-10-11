"""Quy trình Nháp → Chuẩn → Hoàn thiện, không benchmark hay tự đổi checkpoint."""
import math

from .system_tags import WAI_DEFAULTS

WORKFLOW_PRESETS = {
    "Nháp — thử bố cục, không Hires": "draft",
    "Chuẩn — ảnh gốc, tiết kiệm VRAM": "standard",
    "Hoàn thiện — Hires 1.5×": "final",
}
DEFAULT_WORKFLOW = "Chuẩn — ảnh gốc, tiết kiệm VRAM"
SAMPLERS = ["Euler a", "Euler", "DPM++ 2M Karras", "DPM++ 2M SDE Karras",
            "DPM++ 3M SDE Karras", "UniPC"]


def workflow_settings(label, defaults=None, sampler=None):
    base = dict(WAI_DEFAULTS if defaults is None else defaults)
    mode = WORKFLOW_PRESETS.get(label, "standard")
    steps = min(base["steps"], 18) if mode == "draft" else base["steps"]
    return (steps, base["cfg_scale"], sampler or base["sampler_name"], mode == "final",
            1.5, base["hr_second_pass_steps"], 0.35 if mode == "final" else 0.4)


def workflow_note(label):
    mode = WORKFLOW_PRESETS.get(label, "standard")
    text = {"draft": "Thử bố cục trước: ≤18 bước (HSWQ giữ 10), Hires tắt.",
            "standard": "Giữ tham số đúng biến thể; Hires tắt để chọn ảnh/seed trước.",
            "final": "Hires 1.5×, denoise 0.35; tự đặt 1 ảnh/lượt. Giữ sampler, seed và kích thước gốc đã chọn; bật Hires vẫn có thể thay đổi chi tiết."}[mode]
    return text + " Nhiều ảnh được chạy tuần tự (batch_size=1), không phải benchmark GPU."


def _number(value, name, minimum, maximum, integer=False):
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} phải là số.") from None
    if not math.isfinite(n) or not minimum <= n <= maximum or (integer and n != int(n)):
        raise ValueError(f"{name} phải trong [{minimum}, {maximum}]" + (" và là số nguyên." if integer else "."))
    return int(n) if integer else n


def validate_generation(body):
    """Fail sớm trước HTTP; không gửi NaN, sai seed/kích thước hay ảnh vượt budget."""
    body = dict(body)
    if not isinstance(body.get("prompt"), str) or not body["prompt"].strip():
        raise ValueError("Chưa có positive prompt.")
    for key in ("width", "height"):
        body[key] = _number(body[key], key, 512, 2048, True)
        if body[key] % 64:
            raise ValueError("Kích thước SDXL phải chia hết cho 64.")
    body["steps"] = _number(body["steps"], "Steps", 1, 150, True)
    body["cfg_scale"] = _number(body["cfg_scale"], "CFG", 0.1, 30)
    body["seed"] = _number(body["seed"], "Seed", -1, 4294967295, True)
    body["batch_size"] = _number(body.get("batch_size", 1), "Batch", 1, 4, True)
    body["n_iter"] = _number(body.get("n_iter", 1), "Số ảnh", 1, 16, True)
    if body["batch_size"] * body["n_iter"] > 16:
        raise ValueError("Tối đa 16 ảnh/lượt; ưu tiên batch_size=1.")
    if body.get("enable_hr"):
        body["hr_scale"] = _number(body["hr_scale"], "Hires scale", 1, 2)
        body["hr_second_pass_steps"] = _number(body["hr_second_pass_steps"], "Hires steps", 0, 150, True)
        body["denoising_strength"] = _number(body["denoising_strength"], "Denoise", 0, 1)
        target_pixels = body["width"] * body["height"] * body["hr_scale"] ** 2
        if target_pixels > 2048 * 2048:
            raise ValueError("Ảnh Hires vượt 4 megapixel: giảm scale/kích thước gốc, hoặc tắt Hires để tránh quá tải VRAM.")
    return body


def generation_metadata(info, payload, count):
    """State riêng từng session, chỉ lưu metadata cần dùng lại seed, không lưu ảnh."""
    seeds = info.get("all_seeds")
    if not isinstance(seeds, list):
        seeds = [info.get("seed")]
    # Không lọc rồi dồn index: seed hỏng của ảnh 0 không được biến thành seed ảnh 1.
    seeds = [s if type(s) is int and 0 <= s <= 4294967295 else None for s in seeds[:count]]
    offset = info.get("index_of_first_image", 0)
    if type(offset) is not int or not 0 <= offset < count:
        offset = 0
    return {"seeds": seeds, "grid_offset": offset, "width": payload["width"], "height": payload["height"],
            "steps": payload["steps"], "cfg_scale": payload["cfg_scale"],
            "sampler_name": payload["sampler_name"]}


def seed_at(metadata, image_index=0):
    seeds = (metadata or {}).get("seeds", [])
    try:
        index = int(image_index)
    except (TypeError, ValueError):
        return None
    if index != image_index:
        return None
    index -= (metadata or {}).get("grid_offset", 0)
    if not 0 <= index < len(seeds):
        return None
    return seeds[index]


def generation_error(exc):
    message = str(exc).lower()
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            # Inspect privately for OOM only, never show a raw config/log/API error body.
            message += " " + str(response.json()).lower()
        except (ValueError, TypeError):
            pass
    if "out of memory" in message or "cuda oom" in message:
        return "❌ Hết VRAM. Tắt Hires, dùng 1024×1024/832×1216, batch_size=1 và chờ tác vụ khác kết thúc; không cần tải lại checkpoint."
    return f"❌ Sinh ảnh thất bại ({type(exc).__name__}). Kiểm tra Forge/API và diagnostics; prompt và tham số của bạn vẫn được giữ."
