"""Bộ dựng prompt tiếng Việt cho WAI-Illustrious v17 — app Gradio độc lập.

Chạy ở đâu cũng được, miễn là trỏ tới một Forge đang bật `--api`:

    python3 colab/prompt_builder.py                        # mặc định 127.0.0.1:7860
    python3 colab/prompt_builder.py --forge-url http://... --port 7861
    python3 colab/prompt_builder.py --demo                 # không cần Forge/GPU

Tính năng:
  1. Dựng prompt  — tra tag bằng tiếng Việt (không cần gõ dấu), gom nhóm, xếp thứ tự
                    prompt đúng chuẩn Illustrious/WAI, sinh negative tự động.
  2. Dịch prompt  — dán prompt tiếng Anh, xem nghĩa tiếng Việt của từng tag.
  3. Hướng dẫn    — tham số WAI v17 lấy từ thẻ model và cách chạy trên Colab.
"""

import argparse
import json
from functools import lru_cache
from pathlib import Path
import os
import sys
import time

import gradio as gr
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from prompt_lib import (ACTIVE_PROFILE_ID, CHUNK_TOKENS, GROUP_LABELS, BROWSE_GROUPS,  # noqa: E402
                        CATEGORY_NAMES, MODEL_PROFILES, NEGATIVE_PRESETS,
                        QUALITY_PRESETS, RATINGS, SIZE_PRESETS, UPSCALERS, WAI_DEFAULTS,
                        PromptBuilder, StyleLibrary, TagIndex, audit_prompt, compact_prompt,
                        pick_upscaler, summary_line)
from prompt_lib.api import decode_generation_response
from prompt_lib.history import ImageHistory, forge_output_roots
from prompt_lib.history_ui import HistoryPanel
from prompt_lib.editing import replace_or_append, convert_tags
from prompt_lib.generate import (GenerationJob, advice_for, busy_message, format_duration,
                                 interrupt, payload_warnings, ping, progress_info, read_timeout,
                                 status_line, timeouts, wait_diagnosis)
from prompt_lib.workflow import (DEFAULT_WORKFLOW, WORKFLOW_PRESETS, SAMPLERS,
                                 workflow_settings, workflow_note, validate_generation,
                                 generation_metadata, generation_error, seed_at)

INDEX = None
BUILDER = None
STYLES = None
STYLE_HEADERS = ["tag", "nghĩa", "số ảnh", "độ mạnh", "nhóm"]
NO_PRESET = "(không dùng công thức)"


def profile_note():
    """Dòng ghi chú biến thể model đang áp dụng (do colab/install.sh export).

    Chọn `--model hswq` khi cài thì tham số mặc định đã tự đổi thành CFG 1.0 /
    steps 10; dòng này nói rõ cho người dùng biết vì sao số khác thẻ model FP16.
    """
    from prompt_lib.system_tags import profile_environment
    mid = ACTIVE_PROFILE_ID or profile_environment().get("WAI_PROFILE_MODEL_ID") or "fp16"
    prof = MODEL_PROFILES.get(mid)
    label = prof["label"] if prof else "Checkpoint tuỳ chỉnh (kiểm tra tham số theo thẻ model của bạn)"
    return (
        f"\n_Biến thể model: **{mid}** — {label} "
        f"(mặc định CFG {WAI_DEFAULTS['cfg_scale']}, steps {WAI_DEFAULTS['steps']}, "
        f"{WAI_DEFAULTS['sampler_name']}, clip skip {WAI_DEFAULTS['clip_skip']})._\n"
    )
CFG = {"forge_url": "http://127.0.0.1:7860", "demo": False,
       "forge_dir": os.environ.get("FORGE_DIR", "/content/sd-webui-forge-neo"), "history_dir": None}

# --- Lớp tương thích Gradio -------------------------------------------------
# Forge Neo chạy Gradio 4.40, còn môi trường mới có thể là Gradio 5/6, nơi
# `show_copy_button` đã bị bỏ và `theme` chuyển từ Blocks() sang launch().
# App này phải chạy được ở cả hai nơi nên các tham số khác biệt được gom lại đây.
GRADIO_MAJOR = int(str(getattr(gr, "__version__", "4")).split(".")[0] or 4)
COPY_BTN = {"show_copy_button": True} if GRADIO_MAJOR < 6 else {}
BLOCKS_THEME = {"theme": gr.themes.Soft()} if GRADIO_MAJOR < 6 else {}
LAUNCH_THEME = {"theme": gr.themes.Soft()} if GRADIO_MAJOR >= 6 else {}

RESULT_HEADERS = ["tag (tiếng Anh)", "nghĩa tiếng Việt", "category", "số ảnh", "nhóm"]
RATING_CHOICES = [r["label"] for r in RATINGS]
RATING_BY_LABEL = {r["label"]: r["id"] for r in RATINGS}


# ------------------------------------------------------------------ tiện ích
def _row(results):
    return [[r.tag, r.vi or f"{r.tag.replace('_', ' ')} (từ mượn)",
             CATEGORY_NAMES.get(r.category, "Hệ thống"), r.post_count,
             GROUP_LABELS.get(r.group, r.group)] for r in results]


def _tags(results):
    return [r.tag for r in results]


def _merge(selected, new_tags):
    for tag in new_tags:
        selected = replace_or_append(selected, tag, INDEX)
    return selected


def do_convert(selected):
    converted, changes, unknown = convert_tags(selected, INDEX)
    note = "✅ Đã thay " + str(len(changes)) + " mục Việt/alias → Anh, giữ tag khác và trọng số."
    if unknown:
        note += " Chưa xác định: " + ", ".join(unknown) + "; giữ nguyên, hãy chọn kết quả cụ thể."
    return converted, note


def use_image_seed(metadata, image_index):
    seed = seed_at(metadata, image_index)
    if seed is None:
        return gr.skip(), "Chọn một ảnh đã sinh trước (không chọn ảnh lưới)."
    return seed, f"🔒 Dùng lại seed {seed}; giữ kích thước gốc/prompt để so sánh."


def on_image_pick(evt: gr.SelectData):
    return evt.index if isinstance(evt.index, int) else evt.index[0]


def set_workflow(label, sampler=None):
    count = 1 if WORKFLOW_PRESETS.get(label) == "final" else gr.skip()
    return (*workflow_settings(label, sampler=sampler), workflow_note(label), count)


def fetch_upscalers(url=None, timeout=8):
    """Hỏi Forge danh sách upscaler THỰC SỰ có (GET /sdapi/v1/upscalers).

    Cần thiết vì Forge Neo đặt tên scaler theo tên file trong models/ESRGAN
    (RealESRGAN_x4plus_anime_6B) còn A1111 dùng "R-ESRGAN 4x+ Anime6B".
    """
    url = (url or CFG["forge_url"]).rstrip("/")
    try:
        r = requests.get(f"{url}/sdapi/v1/upscalers", timeout=timeout)
        r.raise_for_status()
        return [u.get("name") for u in r.json() if u.get("name")]
    except Exception:                            # noqa: BLE001
        return []


def forge_alive(url=None, timeout=6):
    url = (url or CFG["forge_url"]).rstrip("/")
    try:
        r = requests.get(f"{url}/sdapi/v1/options", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            model = data.get("sd_model_checkpoint")
            if not isinstance(model, str) or not model.strip() or model.lower() == "none":
                return False, f"⚠️ Đã nối được Forge tại `{url}` nhưng **chưa chọn Checkpoint**. Chạy bộ cài với launch/verify."
            if data.get("forge_preset") == "xl" and not data.get("forge_checkpoint_xl"):
                return False, "⚠️ Forge thấy model nhưng preset XL chưa có checkpoint. Cập nhật bộ cài mới nhất rồi restart."
            return True, f"✅ Đã nối được Forge tại `{url}`\n\nCheckpoint đang chọn: `{model}` (nạp trọng số khi sinh ảnh)."
    except Exception as exc:                      # noqa: BLE001
        return False, f"❌ Không nối được Forge tại `{url}`\n\n`{type(exc).__name__}: {exc}`"
    return False, f"❌ Forge trả về mã lỗi {r.status_code}"


# ------------------------------------------------------------------ tab dựng prompt
def do_search(query, cats, limit, allow_nsfw):
    if not (query or "").strip():
        return [], [], "Gõ tiếng Việt hoặc tiếng Anh để tìm tag."
    cat_ids = None
    if cats:
        cat_ids = {int(k) for k, v in CATEGORY_NAMES.items() if v in cats}
    results = INDEX.search(query, cats=cat_ids, limit=int(limit))
    if not allow_nsfw:
        results = [r for r in results if r.group != "sexual"]
    if not results:
        return [], [], f"Không tìm thấy tag nào cho “{query}”."
    best = results[0]
    note = (f"Tìm “{query}” → **{len(results)}** kết quả. Tốt nhất: `{best.tag}` "
            f"({best.vi or 'từ mượn'}), {best.post_count:,} ảnh.")
    return _row(results), _tags(results), note


def do_browse(group, limit, allow_nsfw):
    if not group:
        return [], [], "Chọn một nhóm để duyệt."
    key = next((g for g in BROWSE_GROUPS if GROUP_LABELS[g] == group), group)
    results = INDEX.top_in_group(key, limit=int(limit), min_count=20)
    if not allow_nsfw:
        results = [r for r in results if r.group != "sexual"]
    total = INDEX.group_sizes(20).get(key, 0)
    note = (f"Nhóm **{GROUP_LABELS.get(key, key)}**: {total:,} tag có ≥20 ảnh, "
            f"đang hiện {len(results)} tag phổ biến nhất.")
    return _row(results), _tags(results), note


# ------------------------------------------------------------- mục chọn phong cách vẽ
def style_ready():
    return STYLES is not None and STYLES.loaded


def style_group_choices():
    # "Tất cả (506 tag — mọi nhóm)" đứng đầu: mặc định danh sách tick hiện đủ tag.
    return STYLES.group_choices() if style_ready() else []


def style_preset_choices():
    return [NO_PRESET] + (STYLES.preset_names() if style_ready() else [])


STYLE_MISSING = ("Chưa nạp được `style_tags.csv`. Chạy "
                 "`python3 tools/find_style_tags.py`.")


def style_scope_label(group):
    """Nhãn phạm vi để in trong ghi chú: "Tất cả" hoặc tên nhóm đang chọn."""
    if not style_ready() or STYLES.is_all(group):
        return "Tất cả"
    return str(group)


def style_initial_note():
    """Ghi chú mở màn: nói rõ đang hiện đủ tag, không có tag nào bị ẩn."""
    if not style_ready():
        return STYLE_MISSING
    groups = len(STYLES.groups())
    return (f"Đang hiện **{len(STYLES)}** tag phong cách của **tất cả {groups} nhóm** — "
            "không tag nào bị ẩn. Chọn **Nhóm phong cách** ở trên để lọc, gõ ô tìm để "
            "lọc nhanh, hoặc chọn một **công thức sẵn**.\n\n"
            "_Tick tag muốn dùng rồi bấm **Thêm tag phong cách**; chỉ nên chọn 1 chất liệu "
            "+ 1 kỹ thuật (+ 1 ánh sáng)._")


def do_style_group(group, query, checked=None):
    """Đổi nhóm / gõ tìm → nạp lại danh sách tag phong cách để tick.

    Luôn trả `visible=True` và danh sách đầy đủ của phạm vi; tag đang tick mà vẫn
    còn trong phạm vi mới thì được giữ, nên gõ tìm không làm mất tag đã chọn.
    """
    if not style_ready():
        return (gr.update(choices=[], value=[], visible=True), [], STYLE_MISSING,
                gr.update(visible=True))
    choices = STYLES.choices(group, query or "")
    keep = [label for label in (checked or []) if label in set(choices)]
    rows = STYLES.rows(STYLES.tags_of(choices))
    scope = style_scope_label(group)
    if (query or "").strip():
        note = f"Tìm “{query}” trong **{scope}**: {len(choices)} tag."
    else:
        note = f"Nhóm **{scope}** — " + STYLES.summary(group)
    note += ("\n\n_Tick tag muốn dùng rồi bấm **Thêm tag phong cách**; chỉ nên chọn 1 chất liệu "
             "+ 1 kỹ thuật (+ 1 ánh sáng)._")
    # Gõ tìm thì thu bảng công thức lại để danh sách tag không bị đẩy xuống.
    showcase = gr.update(visible=not (query or "").strip())
    return gr.update(choices=choices, value=keep, visible=True), rows, note, showcase


def do_style_preset(name, group=None):
    """Chọn công thức sẵn → tick sẵn đúng bộ tag của công thức.

    Các tag khác vẫn nằm trong danh sách (xếp sau), không bị ẩn đi.
    """
    if not style_ready():
        return gr.update(visible=True), [], STYLE_MISSING
    if name not in STYLES.preset_names():
        return gr.update(visible=True), [], "Chọn một công thức ở danh sách bên trên."
    tags = STYLES.preset(name)
    labels = [STYLES.info(t).label() for t in tags]
    note = (f"🎨 **{name}** — {STYLES.preset_note(name)}.\n\n"
            f"Đã tick sẵn {len(tags)} tag: " + ", ".join(f"`{t}`" for t in tags)
            + f"\n\nDanh sách vẫn hiện đủ {STYLES.group_count(group)} tag "
              "(tag của công thức nằm trên cùng). Bấm **Thêm tag phong cách** để đưa vào prompt.")
    return (gr.update(choices=STYLES.choices_with(labels, group), value=labels, visible=True),
            STYLES.rows(tags), note)


def do_style_add(selected, checked):
    """Ghép các tag đã tick vào danh sách tag của prompt."""
    tags = STYLES.tags_of(checked) if style_ready() else []
    if not tags:
        return selected, "Chưa tick tag phong cách nào để thêm."
    weak = [t for t in tags if (STYLES.info(t) and STYLES.info(t).post_count < 300)]
    note = "✅ Đã thêm " + ", ".join(f"`{t}`" for t in tags)
    if len(tags) > 3:
        note += "\n\n⚠️ Từ 4 tag phong cách trở lên model dễ trung bình hoá — nên bỏ bớt."
    if weak:
        note += ("\n\n⚠️ Tag ít hơn 300 ảnh nên ảnh hưởng yếu: "
                 + ", ".join(f"`{t}`" for t in weak) + ".")
    return _merge(selected, tags), note


def on_pick(state, selected, evt: gr.SelectData):
    """Bấm một dòng kết quả -> thay mục Việt tương ứng hoặc thêm nếu chưa có.

    Lưu ý: Gradio luôn đặt `evt` ở cuối danh sách tham số, nên thứ tự ở đây phải là
    (state, selected, evt) cho khớp inputs=[state, selected].
    """
    tags = state or []
    if not tags or evt.index is None:
        return selected, ""
    row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    if not (0 <= int(row) < len(tags)):
        return selected, ""
    tag = tags[int(row)]
    return _merge(selected, [tag]), f"Đã chọn/thay `{tag}` — {INDEX.label_of(tag)}"


def do_random(n, seed, allow_nsfw, selected):
    results = INDEX.random_tags(int(n), seed=int(seed) if seed >= 0 else None,
                                min_count=500, allow_nsfw=allow_nsfw)
    tags = _tags(results)
    note = "Gợi ý ngẫu nhiên: " + ", ".join(f"`{t}`" for t in tags)
    return _merge(selected, tags), note


# ------------------------------------------------------------- prompt dài (CLIP 75 token)
def length_report(prompt):
    """Báo cáo độ dài; `group_of` giúp chỉ xếp cặp trùng nghĩa khi cùng nhóm."""
    group_of = INDEX.group_of if INDEX is not None else None
    return audit_prompt(prompt, group_of=group_of)


def length_markdown(rep):
    """Khối Markdown giải thích độ dài + lời khuyên cho người dùng."""
    head = (f"### 📏 {summary_line(rep)}\n"
            f"Mức: **{rep['level']}** · ngân sách khuyến nghị **≤ {rep['budget']} token** "
            f"(mỗi cửa sổ CLIP đọc {CHUNK_TOKENS} token)")
    return head + "\n\n" + "\n\n".join(f"- {line}" for line in rep["advice"])


def do_length(prompt):
    """Nút 'Đo độ dài prompt' → bảng cửa sổ + lời khuyên."""
    if not (prompt or "").strip():
        return "Chưa có prompt. Bấm **🪄 Dựng prompt** trước.", []
    rep = length_report(prompt)
    return length_markdown(rep), rep["window_rows"]


def do_compact(prompt):
    """Nút 'Nén' → bỏ tag trùng nghĩa/trùng lặp, giữ nguyên thứ tự và chi tiết riêng."""
    if not (prompt or "").strip():
        return prompt, ("Chưa có prompt. Bấm **🪄 Dựng prompt** trước."), []
    group_of = INDEX.group_of if INDEX is not None else None
    new_prompt, removed = compact_prompt(prompt, group_of=group_of)
    rep = length_report(new_prompt)
    note = length_markdown(rep)
    if removed:
        note = (f"✂️ Đã bỏ **{len(removed)}** tag trùng nghĩa/trùng lặp: "
                + ", ".join(f"`{t}`" for t in removed) + "\n\n" + note)
    else:
        note = "Không thấy tag trùng nghĩa nào để bỏ.\n\n" + note
    return new_prompt, note, rep["window_rows"]


LONG_PROMPT_TIPS = """**Vì sao prompt dài bị rơi chi tiết:** CLIP chỉ đọc **75 token** mỗi cửa sổ;
token càng xa đầu prompt càng ít trọng số. Chi tiết nằm ở cửa sổ 3 trở đi gần như chỉ còn
tác dụng gợi ý, còn cửa sổ 1 quyết định bố cục.

- **Ngân sách:** ≤ 75 token = chắc · 76–150 = còn tốt · > 150 = bắt đầu loãng.
- **Thứ tự:** chi tiết bắt buộc (chủ thể, hành động, trang phục chính) lên đầu; hoạ sĩ, meta,
  phong cách xuống cuối — app đã tự xếp theo thứ tự Illustrious.
- **Bật “Chèn BREAK giữa các nhóm”** để mỗi nhóm vào một cửa sổ riêng, tag không bị cắt đôi.
- **Bỏ tag trùng nghĩa** (`eyes` khi đã có `blue_eyes`) và tag < 300 ảnh — chúng ăn token
  mà gần như không tác dụng.
- **Quá 150 token thật:** chia 2 lượt — lượt 1 dựng bố cục, lượt 2 img2img denoise 0.35–0.45
  thêm chi tiết. Chi tiết dài nên thêm ở lượt 2, không nhồi vào prompt đầu.
- Chi tiết đầy đủ + ví dụ: `PROMPT_DAI.md` ở thư mục gốc repo.
"""


def do_build(selected, description, rating_label, quality, negative_preset,
             extra_pos, extra_neg, artist_prefix, use_break):
    rating_id = RATING_BY_LABEL.get(rating_label, "general")
    out = BUILDER.assemble(selected, description=description, rating_id=rating_id,
                           quality_preset=quality, extra_positive=extra_pos,
                           artist_prefix=artist_prefix, use_break=use_break)
    out["negative"] = BUILDER.negative(rating_id, negative_preset, extra_neg)

    rows = [[GROUP_LABELS.get(g, g), ", ".join(tags)] for g, tags in out["groups"].items()]
    notes = []
    if out["unresolved"]:
        notes.append("⚠️ Không tra được trong kho, giữ nguyên như bạn gõ: "
                     + ", ".join(f"`{t}`" for t in out["unresolved"]))
    notes.append(f"✅ Prompt có **{out['count']}** tag, xếp theo "
                 f"{len(out['groups'])} nhóm đúng thứ tự Illustrious/WAI.")

    # Độ dài: CLIP chỉ đọc 75 token mỗi cửa sổ nên prompt dài dễ rơi chi tiết.
    rep = length_report(out["prompt"])
    icon = "🟢" if rep["tokens"] <= CHUNK_TOKENS else ("🟡" if rep["within_budget"] else "🔴")
    notes.append(f"{icon} {summary_line(rep)} — "
                 + (rep["advice"][0] if rep["advice"] else ""))
    if rep["late_count"]:
        notes.append(f"⚠️ {rep['late_count']} tag nằm sau token {CHUNK_TOKENS * 2} "
                     "(bị loãng) — mở mục **📏 Prompt dài** để xem cửa sổ nào chứa gì.")
    return out["prompt"], out["negative"], out["vi_preview"], rows, "\n\n".join(notes)


def prepare_generation(prompt, negative, size_label, steps, cfg_scale, sampler, seed,
                       batch, enable_hr, hr_scale, hr_steps, denoise, upscaler, url):
    """Chuẩn bị payload + kiểm tra trước khi gửi Forge.

    Trả `(payload, lỗi, ghi_chú_upscaler, base_url)`. `payload=None` nghĩa là dừng lại và
    hiện `lỗi` cho người dùng (demo/chưa chọn model/tham số sai).
    """
    if not (prompt or "").strip():
        return None, "Chưa có prompt. Bấm **Dựng prompt** trước.", "", ""
    if CFG["demo"]:
        return None, ("🧪 **Chế độ demo** (không có GPU/Forge): app chỉ dựng prompt. "
                      "Chạy notebook Colab để sinh ảnh thật."), "", ""
    overrides = {
        "steps": steps, "cfg_scale": cfg_scale, "sampler_name": sampler,
        "seed": seed, "batch_size": 1, "n_iter": batch,
        "enable_hr": bool(enable_hr), "hr_scale": hr_scale,
        "hr_second_pass_steps": hr_steps, "denoising_strength": denoise,
        "hr_upscaler": upscaler, "override_settings": {"clip_stop_at_last_layers": WAI_DEFAULTS["clip_skip"]},
    }
    if size_label in SIZE_PRESETS:
        overrides["width"], overrides["height"] = SIZE_PRESETS[size_label]
    overrides.update(save_images=True, send_images=True)
    try:
        payload = validate_generation(BUILDER.payload(prompt, negative, overrides))
    except (TypeError, ValueError) as exc:
        return None, f"❌ Tham số không hợp lệ: {exc}", "", ""
    base = (url or CFG["forge_url"]).rstrip("/")

    # backend có thể không có đúng tên upscaler ta chọn -> tự đổi sang bản gần nhất
    swapped = ""
    available = fetch_upscalers(base) if payload.get("enable_hr") else []
    if available:
        before = payload.get("hr_upscaler")
        BUILDER.fix_upscaler(payload, available)
        after = payload.get("hr_upscaler")
        if before and after and before != after:
            swapped = (f"↩️ Backend không có upscaler `{before}`, "
                       f"đã tự đổi sang `{after}`.")
    return payload, "", swapped, base


def _finish_generation(response, payload, started, swapped="", warnings=()):
    """Giải mã response + dựng ghi chú kết quả (dùng chung cho sync và stream)."""
    try:
        images, info = decode_generation_response(response.json())
    except Exception as exc:                      # noqa: BLE001
        return [], (f"❌ Response ảnh của Forge không hợp lệ: "
                    f"`{type(exc).__name__}: {exc}`"), {}
    elapsed = time.time() - started
    head = "\n\n".join(x for x in [*warnings, swapped] if x)
    summary = (f"✅ {len(images)} ảnh trong **{elapsed:.1f}s** · seed `{info.get('seed')}` "
               f"· sampler `{info.get('sampler_name')}` · {info.get('width')}×{info.get('height')} "
               f"· CFG {info.get('cfg_scale')} · {info.get('steps')} bước")
    return images, (head + "\n\n" if head else "") + summary, \
        generation_metadata(info, payload, len(images))


def do_generate(prompt, negative, size_label, steps, cfg_scale, sampler, seed,
                batch, enable_hr, hr_scale, hr_steps, denoise, upscaler, url):
    """Sinh ảnh đồng bộ (dùng cho script/test). UI dùng `do_generate_stream` có tiến trình."""
    payload, message, swapped, base = prepare_generation(
        prompt, negative, size_label, steps, cfg_scale, sampler, seed, batch,
        enable_hr, hr_scale, hr_steps, denoise, upscaler, url)
    if payload is None:
        return [], message, {}

    ok, status = forge_alive(base)
    if not ok:
        return [], status, {}

    warnings = payload_warnings(payload)
    endpoint = base + "/sdapi/v1/txt2img"
    started = time.time()
    try:
        # connect ngắn (biết ngay Forge có sống) + read dài (WAI_GEN_TIMEOUT, mặc định 15 phút)
        r = requests.post(endpoint, json=payload, timeout=timeouts())
        r.raise_for_status()
    except Exception as exc:                      # noqa: BLE001
        return [], generation_error(exc, timeout=read_timeout()), {}
    return _finish_generation(r, payload, started, swapped, warnings)


GENERATE_HEAD = ("ℹ️ Đang sinh ảnh. Thời gian thường gặp trên T4: **Nháp ~30–60s**, "
                 "**Chuẩn ~60–90s**, **Hires 1.5× ~3–6 phút** (lần đầu cộng 1–2 phút nạp model). "
                 "Số bên dưới tự cập nhật mỗi giây; kẹt quá lâu thì bấm **⛔ Huỷ job**.")


def do_generate_stream(prompt, negative, size_label, steps, cfg_scale, sampler, seed,
                       batch, enable_hr, hr_scale, hr_steps, denoise, upscaler, url,
                       stop_after=None):
    """Generator cho nút *Sinh ảnh*: mỗi giây đẩy trạng thái, nên UI không bị "treo".

    `stop_after` chỉ dùng cho test: dừng sau N giây và trả về ảnh giả? Không — test dùng
    `stop_after` để giới hạn vòng lặp, không ảnh hưởng production (mặc định None).
    """
    payload, message, swapped, base = prepare_generation(
        prompt, negative, size_label, steps, cfg_scale, sampler, seed, batch,
        enable_hr, hr_scale, hr_steps, denoise, upscaler, url)
    if payload is None:
        yield gr.update(), message, {}
        return

    # Kiểm tra trước: nếu /options không trả lời (Forge đang bận nạp model), thử ping để
    # không chặn oan — ping sống thì vẫn gửi job, chỉ bỏ qua bước xác nhận checkpoint.
    ok, status = forge_alive(base)
    warnings = payload_warnings(payload)
    if not ok:
        alive = ping(base)
        if not alive.get("alive"):
            yield gr.update(), status, {}
            return
        warnings.append("⚠️ Chưa đọc được `/sdapi/v1/options` (Forge đang bận?) nhưng server "
                        "vẫn phản hồi — vẫn gửi prompt, bỏ qua bước xác nhận checkpoint.")

    head = "\n\n".join(x for x in [*warnings, swapped] if x)

    # Forge đang bận job khác: báo rõ thay vì xếp hàng im lặng. Chờ tối đa 20 giây rồi
    # vẫn gửi (job của mình sẽ nằm trong hàng đợi của Forge), để không "treo" vô ích.
    info = progress_info(base)
    waited = 0
    while info.get("busy") and waited < 20:
        yield gr.update(), "\n\n".join(x for x in [
            head, busy_message(info),
            "Đang chờ chỗ trống… bấm **⛔ Huỷ job** nếu muốn dừng cả job đang chạy."] if x), {}
        time.sleep(2)
        waited += 2
        info = progress_info(base)

    job = GenerationJob(base, payload).start()
    started = job.started
    while not job.done:
        if stop_after is not None and job.elapsed > stop_after:
            break
        info = job.progress()
        text = "\n\n".join(x for x in [
            head, GENERATE_HEAD if job.elapsed < 15 else "",
            status_line(job.elapsed, info),
            advice_for(job.elapsed, info, info.get("stalled", 0)),
        ] if x)
        yield gr.update(), text, {}
        time.sleep(1.0)

    if not job.done:
        yield gr.update(), (head + "\n\n" if head else "") + \
            f"⏳ Dừng theo dõi sau {format_duration(job.elapsed)}; Forge vẫn có thể đang chạy. " \
            "Bấm **🔌 Kiểm tra kết nối** để xem trạng thái.", {}
        return

    if job.error is not None:
        yield gr.update(), generation_error(job.error, timeout=read_timeout()), {}
        return

    images, summary, metadata = _finish_generation(job.response, payload, started,
                                                   swapped, warnings)
    yield images, summary, metadata


def do_stop(url):
    """Nút Huỷ: gửi `/sdapi/v1/interrupt` để Forge dừng job đang kẹt."""
    ok, message = interrupt(url or CFG["forge_url"])
    return message


def do_wait_diagnostics(url=None, elapsed=0):
    """Nút 🔎 Chẩn đoán: vì sao app còn "đang chờ Forge trả ảnh"?

    Kiểm tra 3 thứ tách biệt: endpoint tiến trình (2 đường), Forge còn phản hồi HTTP
    không, và 40 dòng cuối `forge.log` (chỉ lấy loại lỗi, không in nội dung).
    """
    lines = wait_diagnosis(url or CFG["forge_url"], elapsed=elapsed)
    return "### 🔎 Chẩn đoán trạng thái sinh ảnh\n\n" + "\n\n".join(lines)


def do_refresh_upscalers(url):
    """Đọc danh sách upscaler từ Forge và cập nhật lại dropdown."""
    if CFG["demo"]:
        return (gr.Dropdown(choices=UPSCALERS, value=UPSCALERS[0], label="Upscaler"),
                "🧪 Chế độ demo: không hỏi được Forge, đang dùng danh sách mặc định.")
    available = fetch_upscalers(url)
    if not available:
        return (gr.Dropdown(choices=UPSCALERS, value=UPSCALERS[0], label="Upscaler"),
                "❌ Không lấy được danh sách upscaler. Forge phải chạy với cờ `--api`.")
    best = pick_upscaler(available)
    return (gr.Dropdown(choices=available, value=best, label="Upscaler"),
            f"✅ Forge có {len(available)} upscaler, đã chọn sẵn `{best}`: "
            + ", ".join(f"`{u}`" for u in available))


def do_reset():
    return "", "Đã xoá hết tag đã chọn."


def do_drop_last(selected):
    parts = [p.strip() for p in str(selected or "").split(",") if p.strip()]
    if not parts:
        return selected, "Không có tag nào để bỏ."
    removed = parts.pop()
    return ", ".join(parts), f"Đã bỏ `{removed}`."


# ------------------------------------------------------------------ tab dịch prompt
def do_explain(prompt):
    """Dán prompt tiếng Anh -> nghĩa tiếng Việt từng tag (dùng chính kho đã dịch)."""
    if not (prompt or "").strip():
        return "", ""
    lines, missing, out_tags = [], [], []
    for chunk in str(prompt).replace("\n", ",").split(","):
        piece = chunk.strip()
        if not piece:
            continue
        tag = piece
        weight = ""
        if piece.startswith("(") and ":" in piece and piece.endswith(")"):
            inner = piece[1:-1]
            head, _, tail = inner.rpartition(":")
            if head and tail.replace(".", "").isdigit():
                tag, weight = head.strip(), f":{tail}"
        vi = INDEX.vi_of(tag) or INDEX.vi_of(tag.replace(" ", "_"))
        if vi:
            lines.append(f"- `{tag}` → **{vi}**" + (f" _(trọng số {weight[1:]})_" if weight else ""))
        else:
            lines.append(f"- `{tag}` → _(không có trong kho, model tự hiểu theo tiếng Anh)_")
            missing.append(tag)
        out_tags.append(tag)
    head = (f"**{len(out_tags)} tag**, dịch được **{len(out_tags) - len(missing)}** "
            f"({100 * (len(out_tags) - len(missing)) // max(len(out_tags), 1)}%).\n\n")
    return head + "\n".join(lines), ", ".join(out_tags)


@lru_cache(maxsize=4)
def _cached_history(roots, cache_dir):
    return ImageHistory(roots, cache_dir)


def image_history():
    forge_dir = Path(CFG["forge_dir"]).expanduser().resolve()
    options = {}
    try:
        with (forge_dir / "config.json").open(encoding="utf-8") as stream:
            options = json.loads(stream.read(1048576))
        if not isinstance(options, dict):
            options = {}
    except (OSError, ValueError):
        pass
    roots = forge_output_roots(forge_dir, options)
    roots.append(Path(ROOT) / "colab" / "outputs")
    if CFG.get("history_dir"):
        roots.append(Path(CFG["history_dir"]).expanduser())
    cache = forge_dir / "outputs" / ".wai-history"
    if CFG.get("history_dir"):
        cache = Path(CFG["history_dir"]).expanduser() / ".wai-history"
    return _cached_history(tuple(str(p) for p in roots), str(cache))


# ------------------------------------------------------------------ giao diện
def build_ui():
    cat_choices = list(CATEGORY_NAMES.values())
    group_choices = [GROUP_LABELS[g] for g in BROWSE_GROUPS]

    with gr.Blocks(title="Bộ dựng prompt tiếng Việt — WAI-Illustrious v17",
                   **BLOCKS_THEME) as demo:
        gr.Markdown(
            "# 🎨 Bộ dựng prompt tiếng Việt cho WAI-Illustrious v17\n"
            f"Nguồn nhắc: **{len(INDEX):,} tag** Danbooru + e621, trong đó "
            f"**{INDEX.stats()['có_nghĩa_tiếng_việt']:,} tag đã có nghĩa tiếng Việt**. "
            "Gõ tiếng Việt (không cần đúng dấu) → nhận tag tiếng Anh → ghép prompt "
            "đúng thứ tự mà model họ Illustrious hiểu tốt nhất."
            + profile_note()
        )

        with gr.Tabs():
            # ------------------------------------------------ TAB 1: dựng prompt
            with gr.Tab("🧩 Dựng prompt"):
                with gr.Row():
                    url_box = gr.Textbox(label="Địa chỉ Forge (API)",
                                         value=CFG["forge_url"], scale=4)
                    btn_check = gr.Button("🔌 Kiểm tra kết nối", scale=1)
                status = gr.Markdown("Chưa kiểm tra kết nối.")

                with gr.Row():
                    with gr.Column(scale=5):
                        gr.Markdown("### 1. Tìm tag")
                        query = gr.Textbox(label="Gõ tiếng Việt hoặc tiếng Anh",
                                           placeholder="áo dài, tóc dài, đồng phục học sinh, "
                                                       "cầm kiếm, hoa anh đào, ao dai...")
                        with gr.Row():
                            cats = gr.Dropdown(cat_choices, label="Giới hạn category",
                                               multiselect=True)
                            limit = gr.Slider(5, 60, value=20, step=5, label="Số kết quả")
                        allow_nsfw = gr.Checkbox(label="Hiện cả tag 18+ khi tìm/duyệt",
                                                 value=False)
                        with gr.Row():
                            btn_search = gr.Button("🔎 Tìm", variant="primary")
                            group_box = gr.Dropdown(group_choices, label="…hoặc duyệt nhóm",
                                                    value=group_choices[0])
                            btn_browse = gr.Button("📚 Duyệt")
                        results = gr.Dataframe(headers=RESULT_HEADERS, interactive=False,
                                               label="Kết quả — BẤM VÀO MỘT DÒNG để chọn/thay tag")
                        note = gr.Markdown("")

                        gr.Markdown("### 2. Chọn phong cách vẽ")
                        with gr.Row():
                            style_group = gr.Dropdown(style_group_choices(),
                                                      value=(style_group_choices() or [None])[0],
                                                      label="Nhóm phong cách", scale=3)
                            style_preset = gr.Dropdown(style_preset_choices(), value=NO_PRESET,
                                                       label="Công thức sẵn (chọn là tick sẵn)",
                                                       scale=4)
                        style_query = gr.Textbox(
                            label="Tìm trong kho phong cách (không cần dấu)",
                            placeholder="màu nước, cel, ukiyo-e, ánh sáng viền, pixel...")
                        style_checked = gr.CheckboxGroup(
                            choices=(STYLES.choices() if style_ready() else []), value=[],
                            label="Tick tag phong cách — đang hiện đủ tag, đổi nhóm để lọc")
                        with gr.Row():
                            btn_style_add = gr.Button("➕ Thêm tag phong cách",
                                                      variant="secondary", scale=3)
                            btn_style_clear = gr.Button("☐ Bỏ tick", scale=1)
                        style_note = gr.Markdown(style_initial_note())
                        style_table = gr.Dataframe(headers=STYLE_HEADERS, interactive=False,
                                                   label="Độ mạnh của từng tag (theo số bài đăng)")
                        with gr.Accordion("📋 12 công thức sẵn — xem tag của từng công thức",
                                          open=False) as style_showcase:
                            gr.Markdown(STYLES.presets_markdown() if style_ready() else "")

                        gr.Markdown("### 3. Tag đã chọn (sửa tay được)")
                        selected = gr.Textbox(label="Danh sách tag", lines=3,
                                              placeholder="1girl, ao_dai, long_hair, "
                                                          "holding_sword, cherry_blossoms")
                        with gr.Row():
                            btn_random = gr.Button("🎲 Ngẫu nhiên")
                            rnd_n = gr.Slider(4, 20, value=8, step=1, label="Số tag")
                            rnd_seed = gr.Number(value=-1, label="Seed (-1 = ngẫu nhiên)",
                                                 precision=0)
                        btn_convert = gr.Button("🔤 Thay mục Việt → tag Anh")
                        with gr.Row():
                            btn_drop = gr.Button("↩️ Bỏ tag cuối")
                            btn_reset = gr.Button("🗑️ Xoá hết")
                        picked = gr.Markdown("")
                    state = gr.State([])

                    with gr.Column(scale=5):
                        gr.Markdown("### 4. Tuỳ chọn prompt")
                        description = gr.Textbox(
                            label="Câu mô tả tiếng Anh (tuỳ chọn; không tự dịch cả câu)",
                            placeholder="A girl in an ao dai, standing under cherry blossoms")
                        with gr.Row():
                            rating = gr.Dropdown(RATING_CHOICES, value=RATING_CHOICES[0],
                                                 label="Mức phân loại nội dung")
                            quality = gr.Dropdown(list(QUALITY_PRESETS), 
                                                  value="Ngắn gọn",
                                                  label="Tag chất lượng")
                        neg_preset = gr.Dropdown(list(NEGATIVE_PRESETS),
                                                 value="WAI khuyến nghị (ngắn)",
                                                 label="Negative mẫu")
                        with gr.Row():
                            artist_prefix = gr.Dropdown(
                                ["", "artist:", "@"], value="",
                                label="Tiền tố tag hoạ sĩ")
                            use_break = gr.Checkbox(label="Chèn BREAK giữa các nhóm",
                                                    value=False)
                        with gr.Row():
                            extra_pos = gr.Textbox(label="Thêm vào positive (tuỳ ý)")
                            extra_neg = gr.Textbox(label="Thêm vào negative (tuỳ ý)")

                        gr.Markdown("### 5. Nháp → Chuẩn → Hoàn thiện")
                        mode = gr.Dropdown(list(WORKFLOW_PRESETS), value=DEFAULT_WORKFLOW, label="Quy trình")
                        mode_note = gr.Markdown(workflow_note(DEFAULT_WORKFLOW))
                        with gr.Row():
                            size = gr.Dropdown(list(SIZE_PRESETS),
                                               value="Dọc cao 832×1216",
                                               label="Kích thước")
                            sampler = gr.Dropdown(
                                SAMPLERS,
                                value=WAI_DEFAULTS["sampler_name"], label="Sampler")
                        with gr.Row():
                            steps = gr.Slider(1, 60, value=WAI_DEFAULTS["steps"], step=1,
                                              label="Số bước (thẻ model: 15–30)")
                            cfg_scale = gr.Slider(0.5, 12, value=WAI_DEFAULTS["cfg_scale"],
                                                  step=0.5, label="CFG (theo biến thể model)")
                        with gr.Row():
                            seed = gr.Number(value=-1, label="Seed (-1 = ngẫu nhiên)",
                                             precision=0)
                            batch = gr.Slider(1, 4, value=1, step=1, label="Số ảnh tuần tự (batch=1)")
                        enable_hr = gr.Checkbox(label="Hires. fix (chỉ bật sau khi chọn ảnh/seed)", value=False)
                        with gr.Row():
                            hr_scale = gr.Slider(1.0, 2.0, value=WAI_DEFAULTS["hr_scale"],
                                                 step=0.05, label="Hires scale")
                            hr_steps = gr.Slider(0, 40, value=WAI_DEFAULTS["hr_second_pass_steps"],
                                                 step=1, label="Hires steps")
                            denoise = gr.Slider(0.1, 0.8, value=WAI_DEFAULTS["denoising_strength"],
                                                step=0.05, label="Denoising (0.35–0.5)")
                        with gr.Row():
                            upscaler = gr.Dropdown(UPSCALERS, value=WAI_DEFAULTS["hr_upscaler"],
                                                   label="Upscaler", scale=4)
                            btn_upscalers = gr.Button("🔄 Nạp từ Forge", scale=1)
                        upscaler_note = gr.Markdown("")

                        btn_build = gr.Button("🪄 Dựng prompt", variant="primary")
                        prompt_out = gr.Textbox(label="Positive prompt (dán vào Forge)",
                                                lines=4, **COPY_BTN)
                        negative_out = gr.Textbox(label="Negative prompt", lines=3,
                                                  **COPY_BTN)
                        build_note = gr.Markdown("")
                        group_table = gr.Dataframe(headers=["Nhóm", "Tag"],
                                                   interactive=False,
                                                   label="Prompt được xếp nhóm thế nào")
                        with gr.Accordion("📏 Prompt dài — đo độ dài & nén để không rơi chi tiết",
                                          open=False):
                            gr.Markdown(LONG_PROMPT_TIPS)
                            with gr.Row():
                                btn_length = gr.Button("📏 Đo độ dài prompt", scale=1)
                                btn_compact = gr.Button("✂️ Nén: bỏ tag trùng nghĩa", scale=1)
                            length_note = gr.Markdown("")
                            chunk_table = gr.Dataframe(
                                headers=["Cửa sổ CLIP", "Token", "Tag trong cửa sổ"],
                                interactive=False,
                                label=f"Mỗi cửa sổ CLIP đọc {CHUNK_TOKENS} token — chi tiết ở cửa sổ 3+ bị loãng")
                        vi_preview = gr.Textbox(label="Xem trước bằng tiếng Việt", lines=6)
                        with gr.Row():
                            btn_generate = gr.Button("🖼️ Sinh ảnh bằng Forge", variant="primary",
                                                     scale=3)
                            btn_stop = gr.Button("⛔ Huỷ job", scale=1)
                            btn_diag = gr.Button("🔎 Chẩn đoán", scale=1)
                        gallery = gr.Gallery(label="Kết quả", columns=2, height=520)
                        gen_note = gr.Markdown("")
                        diag_note = gr.Markdown("")
                        generation_state = gr.State({})
                        image_index = gr.State(0)
                        btn_seed = gr.Button("🔒 Dùng seed của ảnh đã chọn")

            # ------------------------------------------------ TAB 2: dịch prompt
            with gr.Tab("🔤 Dịch prompt Anh → Việt"):
                gr.Markdown("Dán một prompt tiếng Anh (từ Forge, Civitai, hay chỗ khác) "
                            "để xem nghĩa tiếng Việt của từng tag, tra từ chính kho "
                            f"{INDEX.stats()['có_nghĩa_tiếng_việt']:,} bản dịch.")
                with gr.Row():
                    in_prompt = gr.Textbox(label="Prompt tiếng Anh", lines=6,
                                           placeholder="masterpiece, best quality, 1girl, "
                                                       "long_hair, school_uniform, "
                                                       "cherry_blossoms, from_behind")
                    out_explain = gr.Markdown("### Nghĩa tiếng Việt\n_(chưa có gì)_")
                with gr.Row():
                    btn_explain = gr.Button("🔍 Dịch", variant="primary")
                    out_tags = gr.Textbox(label="Chỉ lấy danh sách tag", lines=3,
                                          **COPY_BTN)

            with gr.Tab("🗂️ Ảnh đã tạo"):
                gr.Markdown("App độc lập chỉ đọc ảnh trên máy đang chạy app; Forge ở máy khác cần thư mục ảnh cục bộ (`--history-dir`).")
                history_panel = HistoryPanel(image_history, seed)
            demo.wai_history_panel = history_panel

            # ------------------------------------------------ TAB 3: hướng dẫn
            with gr.Tab("📖 WAI v17 & Colab"):
                gr.Markdown(GUIDE_MD)

        # -------------------------------------------------------------- nối sự kiện
        btn_check.click(lambda u: forge_alive(u)[1], inputs=[url_box], outputs=[status])

        btn_search.click(do_search, inputs=[query, cats, limit, allow_nsfw],
                         outputs=[results, state, note])
        query.submit(do_search, inputs=[query, cats, limit, allow_nsfw],
                     outputs=[results, state, note])
        btn_browse.click(do_browse, inputs=[group_box, limit, allow_nsfw],
                         outputs=[results, state, note])
        results.select(on_pick, inputs=[state, selected], outputs=[selected, picked])

        # mục chọn phong cách vẽ: đổi nhóm / gõ tìm / chọn công thức sẵn.
        # Cả ba event đều trả danh sách tick đầy đủ (visible=True) nên không có tag bị ẩn.
        style_outputs = [style_checked, style_table, style_note, style_showcase]
        style_group.change(do_style_group, inputs=[style_group, style_query, style_checked],
                           outputs=style_outputs, queue=False)
        style_query.change(do_style_group, inputs=[style_group, style_query, style_checked],
                           outputs=style_outputs, queue=False)
        style_query.submit(do_style_group, inputs=[style_group, style_query, style_checked],
                           outputs=style_outputs, queue=False)
        style_preset.change(do_style_preset, inputs=[style_preset, style_group],
                            outputs=[style_checked, style_table, style_note], queue=False)
        btn_style_add.click(do_style_add, inputs=[selected, style_checked],
                            outputs=[selected, picked])
        btn_style_clear.click(lambda: gr.update(value=[]), None, [style_checked], queue=False)

        btn_random.click(do_random, inputs=[rnd_n, rnd_seed, allow_nsfw, selected],
                         outputs=[selected, picked])
        btn_convert.click(do_convert, [selected], [selected, picked], queue=False)
        mode.change(set_workflow, [mode, sampler], [steps, cfg_scale, sampler, enable_hr, hr_scale,
                                                  hr_steps, denoise, mode_note, batch], queue=False)
        gallery.select(on_image_pick, None, [image_index], queue=False)
        btn_seed.click(use_image_seed, [generation_state, image_index], [seed, gen_note], queue=False)
        btn_drop.click(do_drop_last, inputs=[selected], outputs=[selected, picked])
        btn_reset.click(do_reset, inputs=None, outputs=[selected, picked])

        build_inputs = [selected, description, rating, quality, neg_preset,
                        extra_pos, extra_neg, artist_prefix, use_break]
        btn_length.click(do_length, inputs=[prompt_out],
                         outputs=[length_note, chunk_table], queue=False)
        btn_compact.click(do_compact, inputs=[prompt_out],
                          outputs=[prompt_out, length_note, chunk_table], queue=False)
        btn_build.click(do_build, inputs=build_inputs,
                        outputs=[prompt_out, negative_out, vi_preview, group_table,
                                 build_note])

        btn_upscalers.click(do_refresh_upscalers, inputs=[url_box],
                            outputs=[upscaler, upscaler_note])

        # Generator + đọc /progress mỗi giây: Forge chạy bao lâu cũng thấy trạng thái,
        # không còn màn hình "treo"; ⛔ Huỷ gửi /interrupt và dừng luôn vòng theo dõi.
        generation_event = btn_generate.click(
            do_generate_stream,
            inputs=[prompt_out, negative_out, size, steps, cfg_scale, sampler, seed, batch,
                    enable_hr, hr_scale, hr_steps, denoise, upscaler, url_box],
            outputs=[gallery, gen_note, generation_state],
            concurrency_limit=1, concurrency_id="wai_gpu")
        btn_stop.click(do_stop, inputs=[url_box], outputs=[gen_note], queue=False,
                       cancels=[generation_event])
        btn_diag.click(do_wait_diagnostics, inputs=[url_box], outputs=[diag_note],
                       queue=False)
        history_panel.after_generation(generation_event)

        btn_explain.click(do_explain, inputs=[in_prompt],
                          outputs=[out_explain, out_tags])
    return demo


GUIDE_MD = """
## Prompt dài: giữ chi tiết trong ngân sách 75 token

CLIP đọc **75 token** mỗi cửa sổ; tag càng xa đầu prompt càng ít trọng số. Vì vậy:

- **≤ 75 token** (≈ 12–20 tag): model đọc đủ — an toàn nhất.
- **76–150 token**: còn tốt, nhưng chi tiết bắt buộc phải nằm ở nửa đầu.
- **> 150 token**: cửa sổ 3 trở đi gần như vô tác dụng — bấm **✂️ Nén** hoặc chia 2 lượt
  (txt2img dựng bố cục → img2img denoise 0.35–0.45 thêm chi tiết).
- Bật **Chèn BREAK giữa các nhóm** để mỗi nhóm vào một cửa sổ riêng.
- Mục **📏 Prompt dài** trong tab *Dựng prompt* có bảng cửa sổ + nút đo/nén; chi tiết đầy đủ
  ở tệp `PROMPT_DAI.md`.

## Tham số khuyến nghị của WAI-illustrious-SDXL v17.0

Giữ tham số nền theo biến thể model. Quy trình mới ưu tiên chọn bố cục/seed trước,
chỉ bật Hires khi hoàn thiện; chưa benchmark trên GPU trong sandbox.
Bảng dưới dành cho **FP16 gốc**; FP8/INT8/HSWQ dùng profile/quy trình riêng.

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| File model | `waiIllustriousSDXL_v170.safetensors` | 6,5 GB, SHA256 `f116b0c7…bd04` |
| VAE | **đã tích hợp sẵn** | không cần nạp VAE ngoài |
| Sampler | Euler a | |
| Steps | 15–30 | mặc định ở đây là 25 |
| CFG | 5–7 | mặc định FP16 6; không dùng CFG này cho HSWQ |
| Kích thước | khoảng 1 megapixel trở lên | mặc định 832×1216; 1024×1344 khi còn VRAM |
| Hires. fix | mặc định tắt; hoàn thiện 1.5×, denoise 0.35 | FP16 20 bước Hires; HSWQ 10, không bảo đảm tự sửa mọi lỗi |
| Upscaler | R-ESRGAN 4x+ Anime6B | hợp nét anime |
| Clip skip | 2 | |
| Phần mềm | **Forge Neo** | backend của bộ cài trong dự án |

### Quy trình tiết kiệm VRAM
1. Nhập tag Việt, chọn kết quả hoặc bấm **Thay mục Việt → tag Anh**. Không để “áo dài, ao_dai”.
2. Sang mục **2. Chọn phong cách vẽ** nếu muốn đổi chất ảnh: chọn 1 công thức sẵn
   (màu nước, cel-shading, anime 1990, ukiyo-e, pixel…) hoặc tick tay 1 chất liệu + 1 kỹ thuật,
   rồi bấm **➕ Thêm tag phong cách**. Đừng trộn quá 3 tag phong cách.
3. Dựng prompt ngắn: chủ thể, ngoại hình, trang phục, hành động, bối cảnh/góc máy.
   Câu tự nhiên nên viết tiếng Anh; app chỉ dịch tag đã biết, không đoán cả câu.
4. Chọn **Nháp**: FP16 tối đa 18 bước, HSWQ vẫn 10/CFG 1. Hires tắt.
5. Chọn ảnh trong Gallery → **Dùng seed của ảnh đã chọn**, giữ kích thước gốc.
6. **Chuẩn**: FP16 25/CFG 6, FP8/INT8 25/CFG 6.5, HSWQ 10/CFG 1.
7. **Hoàn thiện**: Hires 1.5×/denoise 0.35, tự đặt 1 ảnh/lượt và giữ sampler đã chọn.
   Preset áp lại steps/CFG; seed không bảo đảm kết quả giống hệt khi thay tham số.

Mỗi lượt ảnh được sinh tuần tự, batch_size=1; không tăng batch để tránh tốn VRAM.
DPM++ Karras được tách thành sampler và scheduler; CLIP stop đi qua options override.
Trong Forge native, nút điền chỉ chuyển prompt, hãy tự chỉnh tham số tại txt2img.

### Bốn mức phân loại nội dung
Thẻ model ghi rõ: *"There are four safety rating tags: general, sensitive, nsfw, explicit.
Users are expected to consciously add 'nsfw' to negative prompts to filter inappropriate
content."* → Bộ dựng prompt tự làm việc này: chọn mức nào thì các mức còn lại bị đẩy
sang negative.

### Thứ tự tag mà app tạo ra
`câu mô tả` → chất lượng → phân loại → nguồn → số lượng/chủ thể → nhân vật → series →
loài → ngoại hình → trang phục → biểu cảm → tư thế → hành động → 18+ → đạo cụ →
bối cảnh → góc máy → hoạ sĩ → meta.
Đúng quy ước cộng đồng Illustrious/NoobAI (tag chất lượng đi đầu, tag hoạ sĩ đi cuối).

## Chạy trên Google Colab
Mở `colab/WAI_Illustrious_v17_vi.ipynb` trong Colab, chạy lần lượt các ô:
1. **Cấu hình** — chọn biến thể model, nơi lưu, cách mở tunnel.
2. **Kiểm tra GPU/ổ đĩa.**
3. **Lấy kho prompt** — clone repo này (cần repo public hoặc token).
4. **Cài Forge Neo** — Python 3.13 qua `uv`, PyTorch theo GPU.
5. **Tải WAI v17** — 6,5 GB từ mirror HuggingFace, có kiểm SHA256.
6. **Cắm kho prompt vào tagcomplete** — chép CSV + ghi sẵn `config.json`.
7. **Cài bộ dựng prompt tiếng Việt** — extension tab trong Forge.
8. **Chạy** — mở link `gradio.live`, bấm tab **"Prompt VN"**.

> App Gradio này cũng chạy độc lập được: `python3 colab/prompt_builder.py`,
> rồi trỏ ô "Địa chỉ Forge" tới URL public của Forge trong Colab.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge-url", default=os.environ.get("FORGE_URL",
                                                              "http://127.0.0.1:7860"))
    parser.add_argument("--root", default=None,
                        help="thư mục chứa các file CSV của kho prompt")
    parser.add_argument("--forge-dir", default=CFG["forge_dir"], help="thư mục Forge cục bộ để đọc ảnh đã lưu")
    parser.add_argument("--history-dir", default=None, help="thêm thư mục ảnh cục bộ vào bảng Ảnh đã tạo")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 7861)))
    parser.add_argument("--share", action="store_true", help="tạo link public gradio.live")
    parser.add_argument("--demo", action="store_true",
                        help="không gọi Forge (chỉ dựng prompt) — dùng để xem thử giao diện")
    args = parser.parse_args()

    CFG["forge_url"] = args.forge_url
    CFG["demo"] = args.demo
    CFG["forge_dir"] = args.forge_dir
    CFG["history_dir"] = args.history_dir

    global INDEX, BUILDER, STYLES
    root = args.root or ROOT
    if not os.path.exists(os.path.join(root, "danbooru_e621.csv")):
        raise SystemExit(f"Không thấy danbooru_e621.csv trong {root}. "
                         "Chạy từ thư mục gốc repo hoặc truyền --root.")
    print(f"Đang nạp kho prompt từ {root} ...")
    started = time.time()
    INDEX = TagIndex(root)
    BUILDER = PromptBuilder(INDEX)
    STYLES = StyleLibrary(root)
    print(f"Xong trong {time.time() - started:.1f}s: {len(INDEX):,} tag, "
          f"{INDEX.stats()['có_nghĩa_tiếng_việt']:,} bản dịch tiếng Việt, "
          f"{len(STYLES) if STYLES.loaded else 0} tag phong cách.")

    demo = build_ui()
    demo.queue(default_concurrency_limit=2).launch(
        server_name=args.host, server_port=args.port, share=args.share,
        show_error=True, prevent_thread_lock=False, **LAUNCH_THEME)


if __name__ == "__main__":
    main()
