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
import base64
import io
import os
import sys
import time

import gradio as gr
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from prompt_lib import (GROUP_LABELS, BROWSE_GROUPS, CATEGORY_NAMES, NEGATIVE_PRESETS,  # noqa: E402
                        QUALITY_PRESETS, RATINGS, SIZE_PRESETS, UPSCALERS, WAI_DEFAULTS,
                        PromptBuilder, TagIndex, pick_upscaler)

INDEX = None
BUILDER = None
CFG = {"forge_url": "http://127.0.0.1:7860", "demo": False}

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
    """Thêm tag vào ô đã chọn, không trùng lặp, giữ thứ tự người dùng."""
    current = [p.strip() for p in str(selected or "").split(",") if p.strip()]
    have = {p.split(":")[0].strip().strip("()").lower() for p in current}
    for tag in new_tags:
        if tag and tag.lower() not in have:
            current.append(tag)
            have.add(tag.lower())
    return ", ".join(current)


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
            model = data.get("sd_model_checkpoint", "(chưa chọn model)")
            return True, f"✅ Đã nối được Forge tại `{url}`\n\nModel đang nạp: `{model}`"
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


def on_pick(state, selected, evt: gr.SelectData):
    """Bấm một dòng trong bảng kết quả -> thêm tag đó vào ô đã chọn.

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
    return _merge(selected, [tag]), f"Đã thêm `{tag}` — {INDEX.label_of(tag)}"


def do_random(n, seed, allow_nsfw, selected):
    results = INDEX.random_tags(int(n), seed=int(seed) if seed >= 0 else None,
                                min_count=500, allow_nsfw=allow_nsfw)
    tags = _tags(results)
    note = "Gợi ý ngẫu nhiên: " + ", ".join(f"`{t}`" for t in tags)
    return _merge(selected, tags), note


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
    return out["prompt"], out["negative"], out["vi_preview"], rows, "\n\n".join(notes)


def do_generate(prompt, negative, size_label, steps, cfg_scale, sampler, seed,
                batch, enable_hr, hr_scale, hr_steps, denoise, upscaler, url):
    if CFG["demo"]:
        return [], ("🧪 **Chế độ demo** (không có GPU/Forge): app chỉ dựng prompt. "
                    "Chạy notebook Colab để sinh ảnh thật.")
    overrides = {
        "steps": int(steps), "cfg_scale": float(cfg_scale), "sampler_name": sampler,
        "seed": int(seed), "batch_size": int(batch),
        "enable_hr": bool(enable_hr), "hr_scale": float(hr_scale),
        "hr_second_pass_steps": int(hr_steps), "denoising_strength": float(denoise),
        "hr_upscaler": upscaler, "override_settings": {"clip_stop_at_last_layers": 2},
    }
    if size_label in SIZE_PRESETS:
        overrides["width"], overrides["height"] = SIZE_PRESETS[size_label]
    payload = BUILDER.payload(prompt, negative, overrides)

    ok, status = forge_alive(url)
    if not ok:
        return [], status

    # backend có thể không có đúng tên upscaler ta chọn -> tự đổi sang bản gần nhất
    swapped = ""
    available = fetch_upscalers(url)
    if available:
        before = payload.get("hr_upscaler")
        BUILDER.fix_upscaler(payload, available)
        after = payload.get("hr_upscaler")
        if before and after and before != after:
            swapped = (f"↩️ Backend không có upscaler `{before}`, "
                       f"đã tự đổi sang `{after}`.\n\n")

    endpoint = (url or CFG["forge_url"]).rstrip("/") + "/sdapi/v1/txt2img"
    started = time.time()
    try:
        r = requests.post(endpoint, json=payload, timeout=1800)
        r.raise_for_status()
    except Exception as exc:                      # noqa: BLE001
        return [], f"❌ Sinh ảnh thất bại: `{type(exc).__name__}: {exc}`"
    data = r.json()
    images = []
    for b64 in data.get("images", []):
        images.append(base64.b64decode(b64.split(",", 1)[-1]))
    info = data.get("info", {})
    elapsed = time.time() - started
    summary = swapped + (f"✅ {len(images)} ảnh trong **{elapsed:.1f}s** · seed `{info.get('seed')}` "
               f"· sampler `{info.get('sampler_name')}` · {info.get('width')}×{info.get('height')} "
               f"· CFG {info.get('cfg_scale')} · {info.get('steps')} bước")
    return images, summary


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
                                               label="Kết quả — BẤM VÀO MỘT DÒNG để thêm tag")
                        note = gr.Markdown("")

                        gr.Markdown("### 2. Tag đã chọn (sửa tay được)")
                        selected = gr.Textbox(label="Danh sách tag", lines=3,
                                              placeholder="1girl, ao_dai, long_hair, "
                                                          "holding_sword, cherry_blossoms")
                        with gr.Row():
                            btn_random = gr.Button("🎲 Ngẫu nhiên")
                            rnd_n = gr.Slider(4, 20, value=8, step=1, label="Số tag")
                            rnd_seed = gr.Number(value=-1, label="Seed (-1 = ngẫu nhiên)",
                                                 precision=0)
                        with gr.Row():
                            btn_drop = gr.Button("↩️ Bỏ tag cuối")
                            btn_reset = gr.Button("🗑️ Xoá hết")
                        picked = gr.Markdown("")
                    state = gr.State([])

                    with gr.Column(scale=5):
                        gr.Markdown("### 3. Tuỳ chọn prompt")
                        description = gr.Textbox(
                            label="Câu mô tả tự nhiên (Illustrious hiểu được cả câu)",
                            placeholder="Một cô gái đứng dưới cơn mưa hoa anh đào")
                        with gr.Row():
                            rating = gr.Dropdown(RATING_CHOICES, value=RATING_CHOICES[0],
                                                 label="Mức phân loại nội dung")
                            quality = gr.Dropdown(list(QUALITY_PRESETS), 
                                                  value="WAI khuyến nghị (đầy đủ)",
                                                  label="Tag chất lượng")
                        neg_preset = gr.Dropdown(list(NEGATIVE_PRESETS),
                                                 value="Chuẩn cộng đồng (đầy đủ)",
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

                        gr.Markdown("### 4. Tham số WAI v17")
                        with gr.Row():
                            size = gr.Dropdown(list(SIZE_PRESETS),
                                               value="Chân dung 1024×1344 (khuyến nghị)",
                                               label="Kích thước")
                            sampler = gr.Dropdown(
                                ["Euler a", "Euler", "DPM++ 2M Karras", "DPM++ 2M SDE Karras",
                                 "DPM++ 3M SDE Karras", "UniPC"],
                                value=WAI_DEFAULTS["sampler_name"], label="Sampler")
                        with gr.Row():
                            steps = gr.Slider(10, 40, value=WAI_DEFAULTS["steps"], step=1,
                                              label="Số bước (thẻ model: 15–30)")
                            cfg_scale = gr.Slider(3, 9, value=WAI_DEFAULTS["cfg_scale"],
                                                  step=0.5, label="CFG (thẻ model: 5–7)")
                        with gr.Row():
                            seed = gr.Number(value=-1, label="Seed (-1 = ngẫu nhiên)",
                                             precision=0)
                            batch = gr.Slider(1, 4, value=1, step=1, label="Số ảnh/lượt")
                        enable_hr = gr.Checkbox(label="Bật Hires. fix (v17 tự sửa tay/chân "
                                                      "tốt hơn)", value=True)
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
                        vi_preview = gr.Textbox(label="Xem trước bằng tiếng Việt", lines=6)
                        btn_generate = gr.Button("🖼️ Sinh ảnh bằng Forge", variant="primary")
                        gallery = gr.Gallery(label="Kết quả", columns=2, height=520)
                        gen_note = gr.Markdown("")

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

        btn_random.click(do_random, inputs=[rnd_n, rnd_seed, allow_nsfw, selected],
                         outputs=[selected, picked])
        btn_drop.click(do_drop_last, inputs=[selected], outputs=[selected, picked])
        btn_reset.click(do_reset, inputs=None, outputs=[selected, picked])

        build_inputs = [selected, description, rating, quality, neg_preset,
                        extra_pos, extra_neg, artist_prefix, use_break]
        btn_build.click(do_build, inputs=build_inputs,
                        outputs=[prompt_out, negative_out, vi_preview, group_table,
                                 build_note])

        btn_upscalers.click(do_refresh_upscalers, inputs=[url_box],
                            outputs=[upscaler, upscaler_note])

        btn_generate.click(do_generate,
                           inputs=[prompt_out, negative_out, size, steps, cfg_scale,
                                   sampler, seed, batch, enable_hr, hr_scale, hr_steps,
                                   denoise, upscaler, url_box],
                           outputs=[gallery, gen_note])

        btn_explain.click(do_explain, inputs=[in_prompt],
                          outputs=[out_explain, out_tags])
    return demo


GUIDE_MD = """
## Tham số khuyến nghị của WAI-illustrious-SDXL v17.0

Lấy trực tiếp từ thẻ model (Civitai 827184, version 2883731) và bài thử nghiệm cộng đồng:

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| File model | `waiIllustriousSDXL_v170.safetensors` | 6,5 GB, SHA256 `f116b0c7…bd04` |
| VAE | **đã tích hợp sẵn** | không cần nạp VAE ngoài |
| Sampler | Euler a | |
| Steps | 15–30 | mặc định ở đây là 25 |
| CFG | 5–7 | đừng vượt 6 với nội dung 18+ (da bị "cháy") |
| Kích thước | lớn hơn 1024×1024 | ví dụ 1024×1344 |
| Hires. fix | scale 1.5, 20 bước, denoise 0.35–0.5 | v17 **tự sửa tay/chân tốt hơn hẳn v16** |
| Upscaler | R-ESRGAN 4x+ Anime6B | hợp nét anime |
| Clip skip | 2 | |
| Phần mềm | **forge-neo** (khuyến nghị của tác giả) | hoặc ComfyUI |

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
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 7861)))
    parser.add_argument("--share", action="store_true", help="tạo link public gradio.live")
    parser.add_argument("--demo", action="store_true",
                        help="không gọi Forge (chỉ dựng prompt) — dùng để xem thử giao diện")
    args = parser.parse_args()

    CFG["forge_url"] = args.forge_url
    CFG["demo"] = args.demo

    global INDEX, BUILDER
    root = args.root or ROOT
    if not os.path.exists(os.path.join(root, "danbooru_e621.csv")):
        raise SystemExit(f"Không thấy danbooru_e621.csv trong {root}. "
                         "Chạy từ thư mục gốc repo hoặc truyền --root.")
    print(f"Đang nạp kho prompt từ {root} ...")
    started = time.time()
    INDEX = TagIndex(root)
    BUILDER = PromptBuilder(INDEX)
    print(f"Xong trong {time.time() - started:.1f}s: {len(INDEX):,} tag, "
          f"{INDEX.stats()['có_nghĩa_tiếng_việt']:,} bản dịch tiếng Việt.")

    demo = build_ui()
    demo.queue(default_concurrency_limit=8).launch(
        server_name=args.host, server_port=args.port, share=args.share,
        show_error=True, prevent_thread_lock=False, **LAUNCH_THEME)


if __name__ == "__main__":
    main()
