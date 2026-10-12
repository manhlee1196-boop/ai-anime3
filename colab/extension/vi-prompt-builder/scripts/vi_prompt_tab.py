"""Extension Forge/A1111: thêm tab "Prompt VN" — bộ dựng prompt tiếng Việt.

Dùng chính kho tag Danbooru + e621 đã dịch (prompt_lib) làm bộ nhắc:
tra tag bằng tiếng Việt -> xếp thứ tự prompt chuẩn Illustrious/WAI -> hoặc là điền
thẳng vào ô txt2img, hoặc là gọi API sinh ảnh ngay với tham số của thẻ model v17.

Cài: chép cả thư mục này vào <forge>/extensions/  (không cần là git repo, Forge vẫn nạp
extension cục bộ miễn là có thư mục scripts/).
"""

import os
import sys
from functools import lru_cache
from pathlib import Path

import gradio as gr
import requests

from modules import script_callbacks, shared  # noqa: E402  (Forge cung cấp)

EXT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- tìm prompt_lib
def _repo_root_from_marker():
    """setup_forge.sh ghi đường dẫn repo vào .repo_root khi cài extension."""
    marker = os.path.join(EXT_DIR, ".repo_root")
    try:
        with open(marker, encoding="utf-8") as f:
            path = f.read().strip()
        return path if path and os.path.isdir(path) else ""
    except OSError:
        return ""


# Notebook chép repo vào /content/ai-anime3; cũng cho phép trỏ bằng biến môi trường.
CANDIDATE_ROOTS = [
    _repo_root_from_marker(),
    os.environ.get("VI_PROMPT_ROOT", ""),
    "/content/ai-anime3",
    os.path.join(EXT_DIR, "prompt_lib_bundle"),
    os.path.abspath(os.path.join(EXT_DIR, "..", "..", "..")),
]


def _locate():
    """Trả về (đường dẫn prompt_lib, đường chứa CSV của kho)."""
    for cand in CANDIDATE_ROOTS:
        if not cand or not os.path.isdir(cand):
            continue
        lib_dir = cand if os.path.isdir(os.path.join(cand, "prompt_lib")) \
            else os.path.join(cand, "colab")
        if not os.path.isdir(os.path.join(lib_dir, "prompt_lib")):
            continue
        csv_root = os.path.abspath(os.path.join(lib_dir, ".."))
        if os.path.exists(os.path.join(csv_root, "danbooru_e621.csv")):
            return lib_dir, csv_root
    return None, None


LIB_DIR, CSV_ROOT = _locate()

GRADIO_MAJOR = int(str(getattr(gr, "__version__", "4")).split(".")[0] or 4)
COPY_BTN = {"show_copy_button": True} if GRADIO_MAJOR < 6 else {}
BLOCKS_THEME = {"theme": gr.themes.Soft()} if GRADIO_MAJOR < 6 else {}

if LIB_DIR:
    sys.path.insert(0, LIB_DIR)
    from prompt_lib import (ACTIVE_PROFILE_ID, MODEL_PROFILES, BROWSE_GROUPS, CATEGORY_NAMES, GROUP_LABELS,  # noqa: E402
                            NEGATIVE_PRESETS, QUALITY_PRESETS, RATINGS, SIZE_PRESETS,
                            UPSCALERS, WAI_DEFAULTS, PromptBuilder, TagIndex)

    from prompt_lib.api import decode_generation_response
    from prompt_lib.history import ImageHistory, forge_output_roots
    from prompt_lib.history_ui import HistoryPanel
    from prompt_lib.editing import replace_or_append, convert_tags
    from prompt_lib.workflow import (DEFAULT_WORKFLOW, WORKFLOW_PRESETS, SAMPLERS,
                                     workflow_settings, workflow_note, validate_generation,
                                     generation_metadata, generation_error, seed_at)

    INDEX = TagIndex(CSV_ROOT)
    BUILDER = PromptBuilder(INDEX)
    RATING_BY_LABEL = {r["label"]: r["id"] for r in RATINGS}
    RATING_CHOICES = [r["label"] for r in RATINGS]
else:
    INDEX = BUILDER = None


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


def _forge_url():
    """URL API của chính Forge đang chạy extension này."""
    port = getattr(shared.cmd_opts, "port", 7860) or 7860
    return f"http://127.0.0.1:{port}"


@lru_cache(maxsize=4)
def _cached_history(forge_dir, roots):
    return ImageHistory(roots, Path(forge_dir) / "outputs" / ".wai-history")


def image_history():
    forge_dir = Path(EXT_DIR).parent.parent.resolve()
    roots = forge_output_roots(forge_dir, getattr(shared, "opts", None))
    # Bao gồm ảnh của ví dụ API notebook, không giữ chúng trong State.
    roots.append(Path(CSV_ROOT) / "colab" / "outputs")
    return _cached_history(str(forge_dir), tuple(str(p) for p in roots))


# ------------------------------------------------------------------ các handler
def do_search(query, cats, limit, allow_nsfw):
    if INDEX is None:
        return [], [], LOST_NOTE
    if not (query or "").strip():
        return [], [], "Gõ tiếng Việt hoặc tiếng Anh để tìm tag."
    cat_ids = {int(k) for k, v in CATEGORY_NAMES.items() if v in (cats or [])} or None
    results = INDEX.search(query, cats=cat_ids, limit=int(limit))
    if not allow_nsfw:
        results = [r for r in results if r.group != "sexual"]
    if not results:
        return [], [], f"Không tìm thấy tag nào cho “{query}”."
    best = results[0]
    return (_row(results), _tags(results),
            f"Tìm “{query}” → **{len(results)}** kết quả. Tốt nhất: `{best.tag}` "
            f"({best.vi or 'từ mượn'}), {best.post_count:,} ảnh.")


def do_browse(group, limit, allow_nsfw):
    if INDEX is None or not group:
        return [], [], (LOST_NOTE if INDEX is None else "Chọn một nhóm để duyệt.")
    key = next((g for g in BROWSE_GROUPS if GROUP_LABELS[g] == group), group)
    results = INDEX.top_in_group(key, limit=int(limit), min_count=20)
    if not allow_nsfw:
        results = [r for r in results if r.group != "sexual"]
    total = INDEX.group_sizes(20).get(key, 0)
    return (_row(results), _tags(results),
            f"Nhóm **{GROUP_LABELS.get(key, key)}**: {total:,} tag có ≥20 ảnh, "
            f"đang hiện {len(results)} tag phổ biến nhất.")


def on_pick(state, selected, evt: gr.SelectData):
    tags = state or []
    if not tags or evt.index is None:
        return selected, ""
    row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    if not (0 <= int(row) < len(tags)):
        return selected, ""
    tag = tags[int(row)]
    return _merge(selected, [tag]), f"Đã chọn/thay `{tag}` — {INDEX.label_of(tag)}"


def do_random(n, allow_nsfw, selected):
    if INDEX is None:
        return selected, LOST_NOTE
    results = INDEX.random_tags(int(n), min_count=500, allow_nsfw=allow_nsfw)
    tags = _tags(results)
    return _merge(selected, tags), "Gợi ý: " + ", ".join(f"`{t}`" for t in tags)


def do_build(selected, description, rating_label, quality, negative_preset,
             extra_pos, extra_neg, artist_prefix):
    if BUILDER is None:
        return "", "", [], LOST_NOTE, ""
    rating_id = RATING_BY_LABEL.get(rating_label, "general")
    out = BUILDER.assemble(selected, description=description, rating_id=rating_id,
                           quality_preset=quality, extra_positive=extra_pos,
                           artist_prefix=artist_prefix)
    out["negative"] = BUILDER.negative(rating_id, negative_preset, extra_neg)
    rows = [[GROUP_LABELS.get(g, g), ", ".join(t)] for g, t in out["groups"].items()]
    note = f"✅ **{out['count']}** tag, xếp theo {len(out['groups'])} nhóm."
    if out["unresolved"]:
        note += ("\n\n⚠️ Không tra được, giữ nguyên như bạn gõ: "
                 + ", ".join(f"`{t}`" for t in out["unresolved"]))
    return out["prompt"], out["negative"], rows, note, out["vi_preview"]


def do_generate(prompt, negative, size_label, steps, cfg_scale, sampler, seed,
                enable_hr, hr_scale, denoise, upscaler, hr_steps=None, batch=1):
    """Sinh ảnh qua API của chính Forge (cần bật --api)."""
    import time

    if not (prompt or "").strip():
        return [], "Chưa có prompt. Bấm **Dựng prompt** trước.", {}
    overrides = {
        "steps": steps, "cfg_scale": cfg_scale, "sampler_name": sampler,
        "seed": seed, "batch_size": 1, "n_iter": batch, "enable_hr": bool(enable_hr),
        "hr_scale": hr_scale, "denoising_strength": denoise,
        "hr_upscaler": upscaler, "hr_second_pass_steps": WAI_DEFAULTS["hr_second_pass_steps"] if hr_steps is None else hr_steps,
        "override_settings": {"clip_stop_at_last_layers": WAI_DEFAULTS["clip_skip"]},
    }
    if size_label in SIZE_PRESETS:
        overrides["width"], overrides["height"] = SIZE_PRESETS[size_label]
    overrides.update(save_images=True, send_images=True)
    try:
        payload = validate_generation(BUILDER.payload(prompt, negative, overrides))
    except (TypeError, ValueError) as exc:
        return [], f"❌ Tham số không hợp lệ: {exc}", {}
    url_base = _forge_url()

    # Forge Neo đặt tên upscaler theo tên file, khác A1111 -> hỏi backend rồi tự sửa
    swapped = ""
    try:
        if not payload.get("enable_hr"):
            raise ValueError("Hires tắt; không cần hỏi upscaler")
        r = requests.get(url_base + "/sdapi/v1/upscalers", timeout=10)
        r.raise_for_status()
        available = [u.get("name") for u in r.json() if u.get("name")]
    except Exception:                            # noqa: BLE001
        available = []
    if available:
        before = payload.get("hr_upscaler")
        BUILDER.fix_upscaler(payload, available)
        if before and payload.get("hr_upscaler") != before:
            swapped = (f"↩️ Không có upscaler `{before}`, đã đổi sang "
                       f"`{payload.get('hr_upscaler')}`.\n\n")

    url = url_base + "/sdapi/v1/txt2img"
    started = time.time()
    try:
        r = requests.post(url, json=payload, timeout=1800)
        r.raise_for_status()
    except Exception as exc:                      # noqa: BLE001
        return [], generation_error(exc), {}
    try:
        images, info = decode_generation_response(r.json())
    except Exception as exc:                      # noqa: BLE001
        return [], f"❌ Response ảnh của Forge không hợp lệ: `{type(exc).__name__}: {exc}`", {}
    return images, swapped + (f"✅ {len(images)} ảnh trong {time.time() - started:.1f}s · "
                    f"seed `{info.get('seed')}` · {info.get('width')}×{info.get('height')} · "
                    f"CFG {info.get('cfg_scale')} · {info.get('steps')} bước"), generation_metadata(info, payload, len(images))


LOST_NOTE = (
    "❌ Không tìm thấy `prompt_lib` và các file CSV của kho prompt.\n\n"
    "Hãy đặt biến môi trường `VI_PROMPT_ROOT` trỏ tới thư mục repo "
    "(ví dụ `/content/ai-anime3`) rồi khởi động lại Forge."
)


# ------------------------------------------------------------------ dựng tab
def build_tab():
    with gr.Blocks(**BLOCKS_THEME) as tab:
        if INDEX is None:
            gr.Markdown("## ❌ Thiếu kho prompt\n\n" + LOST_NOTE)
            return tab

        gr.Markdown(
            f"## 🇻🇳 Prompt tiếng Việt cho WAI-Illustrious v17\n"
            f"Kho nhắc: **{len(INDEX):,} tag** Danbooru + e621, "
            f"**{INDEX.stats()['có_nghĩa_tiếng_việt']:,} tag có nghĩa tiếng Việt**. "
            "Gõ tiếng Việt → bấm vào dòng kết quả để thêm tag → **Dựng prompt** → "
            "điền vào txt2img hoặc sinh ảnh ngay.\n\n"
            f"Biến thể: **{ACTIVE_PROFILE_ID or 'fp16'}** · "
            f"CFG {WAI_DEFAULTS['cfg_scale']} · {WAI_DEFAULTS['steps']} bước."
        )

        with gr.Row():
            with gr.Column(scale=5):
                query = gr.Textbox(label="Tìm tag (tiếng Việt, không cần gõ dấu)",
                                   placeholder="áo dài, tóc dài, đồng phục học sinh, ao dai…")
                with gr.Row():
                    cats = gr.Dropdown(list(CATEGORY_NAMES.values()),
                                       label="Giới hạn category", multiselect=True)
                    limit = gr.Slider(5, 60, value=20, step=5, label="Số kết quả")
                allow_nsfw = gr.Checkbox(label="Hiện cả tag 18+", value=False)
                with gr.Row():
                    btn_search = gr.Button("🔎 Tìm", variant="primary")
                    group_box = gr.Dropdown([GROUP_LABELS[g] for g in BROWSE_GROUPS],
                                            label="…hoặc duyệt nhóm",
                                            value=GROUP_LABELS[BROWSE_GROUPS[0]])
                    btn_browse = gr.Button("📚 Duyệt")
                results = gr.Dataframe(
                    headers=["tag", "nghĩa tiếng Việt", "category", "số ảnh", "nhóm"],
                    interactive=False, label="BẤM VÀO MỘT DÒNG để chọn/thay tag")
                note = gr.Markdown("")

                selected = gr.Textbox(label="Tag đã chọn (sửa tay được)", lines=3)
                btn_convert = gr.Button("🔤 Thay mục Việt → tag Anh")
                with gr.Row():
                    btn_random = gr.Button("🎲 Ngẫu nhiên")
                    rnd_n = gr.Slider(4, 20, value=8, step=1, label="Số tag")
                    btn_clear = gr.Button("🗑️ Xoá")
                picked = gr.Markdown("")
            state = gr.State([])

            with gr.Column(scale=5):
                description = gr.Textbox(label="Câu mô tả tiếng Anh (tuỳ chọn; không tự dịch cả câu)",
                                         placeholder="A girl in an ao dai under cherry blossoms")
                with gr.Row():
                    rating = gr.Dropdown(RATING_CHOICES, value=RATING_CHOICES[0],
                                         label="Mức phân loại")
                    quality = gr.Dropdown(list(QUALITY_PRESETS),
                                          value="Ngắn gọn",
                                          label="Tag chất lượng")
                neg_preset = gr.Dropdown(list(NEGATIVE_PRESETS),
                                         value="WAI khuyến nghị (ngắn)",
                                         label="Negative mẫu")
                with gr.Row():
                    artist_prefix = gr.Dropdown(["", "artist:", "@"], value="",
                                                label="Tiền tố hoạ sĩ")
                    extra_pos = gr.Textbox(label="Thêm positive")
                    extra_neg = gr.Textbox(label="Thêm negative")

                btn_build = gr.Button("🪄 Dựng prompt", variant="primary")
                prompt_out = gr.Textbox(label="Positive prompt", lines=4, **COPY_BTN)
                negative_out = gr.Textbox(label="Negative prompt", lines=3, **COPY_BTN)
                build_note = gr.Markdown("")
                group_table = gr.Dataframe(headers=["Nhóm", "Tag"], interactive=False,
                                           label="Cấu trúc prompt")
                vi_preview = gr.Textbox(label="Xem trước tiếng Việt", lines=5)

                # Điền thẳng vào ô txt2img bằng JS (xem javascript/vi_prompt.js)
                btn_fill = gr.Button("📋 Đưa vào txt2img", variant="secondary")
                replace_all = gr.Checkbox(label="Thay toàn bộ prompt đích (mặc định chỉ ghép/thay mục trùng)", value=False)
                btn_undo = gr.Button("↩️ Hoàn tác điền txt2img")
                fill_note = gr.Markdown("", elem_id="vi_prompt_fill_note")

                gr.Markdown("### Nháp → Chuẩn → Hoàn thiện (API)")
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
                                      label="Steps (theo biến thể model)")
                    cfg_scale = gr.Slider(0.5, 12, value=WAI_DEFAULTS["cfg_scale"], step=0.5,
                                          label="CFG (theo biến thể model)")
                    seed = gr.Number(value=-1, label="Seed (-1 = ngẫu nhiên)", precision=0)
                with gr.Row():
                    enable_hr = gr.Checkbox(label="Hires. fix (sau khi chọn ảnh/seed)", value=False)
                    hr_scale = gr.Slider(1.0, 2.0, value=WAI_DEFAULTS["hr_scale"],
                                         step=0.05, label="Hires scale")
                    denoise = gr.Slider(0.1, 0.8, value=WAI_DEFAULTS["denoising_strength"],
                                        step=0.05, label="Denoising")
                    upscaler = gr.Dropdown(UPSCALERS, value=WAI_DEFAULTS["hr_upscaler"],
                                           label="Upscaler")
                with gr.Row():
                    hr_steps = gr.Slider(0, 40, value=WAI_DEFAULTS["hr_second_pass_steps"], step=1, label="Hires steps")
                    batch = gr.Slider(1, 4, value=1, step=1, label="Số ảnh tuần tự (batch=1)")
                btn_generate = gr.Button("🖼️ Sinh ảnh", variant="primary")
                gallery = gr.Gallery(label="Kết quả", columns=2, height=480)
                gen_note = gr.Markdown("")
                generation_state = gr.State({})
                image_index = gr.State(0)
                btn_seed = gr.Button("🔒 Dùng seed của ảnh đã chọn")

        with gr.Accordion("🗂️ Ảnh đã tạo", open=True):
            history_panel = HistoryPanel(image_history, seed)
        tab.wai_history_panel = history_panel

        btn_search.click(do_search, [query, cats, limit, allow_nsfw],
                         [results, state, note])
        query.submit(do_search, [query, cats, limit, allow_nsfw],
                     [results, state, note])
        btn_browse.click(do_browse, [group_box, limit, allow_nsfw],
                         [results, state, note])
        results.select(on_pick, [state, selected], [selected, picked])
        btn_convert.click(do_convert, [selected], [selected, picked], queue=False)
        mode.change(set_workflow, [mode, sampler], [steps, cfg_scale, sampler, enable_hr, hr_scale,
                                                  hr_steps, denoise, mode_note, batch], queue=False)
        gallery.select(on_image_pick, None, [image_index], queue=False)
        btn_seed.click(use_image_seed, [generation_state, image_index], [seed, gen_note], queue=False)
        btn_random.click(do_random, [rnd_n, allow_nsfw, selected], [selected, picked])
        btn_clear.click(lambda: ("", "Đã xoá."), None, [selected, picked])

        btn_build.click(do_build,
                        [selected, description, rating, quality, neg_preset,
                         extra_pos, extra_neg, artist_prefix],
                        [prompt_out, negative_out, group_table, build_note, vi_preview])

        # Điền vào txt2img: chạy hoàn toàn ở phía trình duyệt, không cần Python
        btn_fill.click(fn=None, inputs=[prompt_out, negative_out, replace_all], outputs=None,
                       js="viPromptFill")
        btn_undo.click(fn=None, inputs=None, outputs=None, js="viPromptUndo")

        generation_event = btn_generate.click(do_generate,
                           [prompt_out, negative_out, size, steps, cfg_scale, sampler,
                            seed, enable_hr, hr_scale, denoise, upscaler, hr_steps, batch],
                           [gallery, gen_note, generation_state], concurrency_limit=1, concurrency_id="wai_gpu")
        history_panel.after_generation(generation_event)
    return tab


def on_ui_tabs():
    return [(build_tab(), "Prompt VN", "vi_prompt_tab")]


script_callbacks.on_ui_tabs(on_ui_tabs)
