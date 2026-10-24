"""Extension Forge/A1111: khối "Prompt tiếng Việt" nằm NGAY TRONG tab txt2img.

Trước đây là một tab riêng ("Prompt VN"); tab đó đã bỏ. Toàn bộ chức năng tra tag
tiếng Việt, chọn phong cách và dựng prompt giờ là một accordion (gấp lại được) trong
vùng script của txt2img — ngay trên nút Generate. Bấm **Đưa vào txt2img** để đổ
prompt vào ô Prompt/Negative của txt2img rồi dùng chính nút Generate của Forge.

Không còn gọi API sinh ảnh và không còn album ảnh riêng ở đây: txt2img của Forge đã
có nút Generate + gallery + ảnh đã tạo, dùng chúng thay vì dựng thêm một đường sinh
ảnh thứ hai (dễ lệch tham số và chiếm GPU hai lần).

Cài: chép cả thư mục này vào <forge>/extensions/  (không cần là git repo, Forge vẫn nạp
extension cục bộ miễn là có thư mục scripts/).
"""

import os
import sys

import gradio as gr

from modules.scripts import AlwaysVisible, Script  # noqa: E402  (Forge cung cấp)

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

if LIB_DIR:
    sys.path.insert(0, LIB_DIR)
    from prompt_lib import (ACTIVE_PROFILE_ID, BROWSE_GROUPS, CATEGORY_NAMES, GROUP_LABELS,  # noqa: E402
                            NEGATIVE_PRESETS, QUALITY_PRESETS, RATINGS, WAI_DEFAULTS,
                            PromptBuilder, StyleLibrary, TagIndex,
                            audit_prompt, summary_line, CHUNK_TOKENS)
    from prompt_lib.editing import replace_or_append, convert_tags

    INDEX = TagIndex(CSV_ROOT)
    BUILDER = PromptBuilder(INDEX)
    STYLES = StyleLibrary(CSV_ROOT)
    RATING_BY_LABEL = {r["label"]: r["id"] for r in RATINGS}
    RATING_CHOICES = [r["label"] for r in RATINGS]
else:
    INDEX = BUILDER = None
    STYLES = None

STYLE_HEADERS = ["tag", "nghĩa", "số ảnh", "độ mạnh", "nhóm"]
NO_PRESET = "(không dùng công thức)"


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


# ------------------------------------------------------------- mục chọn phong cách vẽ
def style_ready():
    return STYLES is not None and getattr(STYLES, "loaded", False)


def style_group_choices():
    # "Tất cả (506 tag — mọi nhóm)" đứng đầu: mặc định danh sách tick hiện đủ tag.
    return STYLES.group_choices() if style_ready() else []


def style_preset_choices():
    return [NO_PRESET] + (STYLES.preset_names() if style_ready() else [])


STYLE_MISSING = ("Chưa có `style_tags.csv` trong thư mục repo. Chạy "
                 "`python3 tools/find_style_tags.py` rồi mở lại Forge.")


def style_scope_label(group):
    """Nhãn phạm vi để in trong ghi chú: "Tất cả" hoặc tên nhóm đang chọn."""
    if not style_ready() or STYLES.is_all(group):
        return "Tất cả"
    return str(group)


def style_initial_note():
    """Ghi chú mở màn: đang hiện đủ tag, không tag nào bị ẩn."""
    if not style_ready():
        return STYLE_MISSING
    groups = len(STYLES.groups())
    return (f"Đang hiện **{len(STYLES)}** tag phong cách của **tất cả {groups} nhóm** — "
            "không tag nào bị ẩn. Chọn **Nhóm phong cách** để lọc, gõ ô tìm để lọc nhanh, "
            "hoặc chọn một **công thức sẵn**.\n\n"
            "_Tick tag muốn dùng rồi bấm **Thêm tag phong cách**; chỉ nên chọn "
            "1 chất liệu + 1 kỹ thuật (+ 1 ánh sáng)._")


def do_style_group(group, query, checked=None):
    """Đổi nhóm / gõ tìm → nạp lại danh sách tag phong cách để tick.

    Luôn trả `visible=True`; tag đang tick mà còn trong phạm vi mới thì được giữ.
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
    note += ("\n\n_Tick tag muốn dùng rồi bấm **Thêm tag phong cách**; chỉ nên chọn "
             "1 chất liệu + 1 kỹ thuật (+ 1 ánh sáng)._")
    showcase = gr.update(visible=not (query or "").strip())
    return gr.update(choices=choices, value=keep, visible=True), rows, note, showcase


def do_style_preset(name, group=None):
    """Chọn công thức sẵn → tick sẵn đúng bộ tag; tag khác vẫn hiện, không bị ẩn."""
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
    # CLIP chỉ đọc 75 token/cửa sổ: báo ngay để người dùng biết prompt đã dài quá chưa.
    rep = audit_prompt(out["prompt"], group_of=INDEX.group_of if INDEX is not None else None)
    icon = "🟢" if rep["tokens"] <= CHUNK_TOKENS else ("🟡" if rep["within_budget"] else "🔴")
    note += f"\n\n{icon} **{summary_line(rep)}** — {rep['level']}."
    if rep["late_count"]:
        note += (f" ⚠️ {rep['late_count']} tag nằm sau token {CHUNK_TOKENS * 2} sẽ bị loãng: "
                 "đưa chi tiết quan trọng lên đầu hoặc bật `BREAK`.")
    return out["prompt"], out["negative"], rows, note, out["vi_preview"]


LOST_NOTE = (
    "❌ Không tìm thấy `prompt_lib` và các file CSV của kho prompt.\n\n"
    "Hãy đặt biến môi trường `VI_PROMPT_ROOT` trỏ tới thư mục repo "
    "(ví dụ `/content/ai-anime3`) rồi khởi động lại Forge."
)


# --------------------------------------------------- khối UI trong tab txt2img
ACCORDION_LABEL = "🇻🇳 Prompt tiếng Việt — tra tag, phong cách, dựng prompt"


def build_ui():
    """Dựng khối prompt Việt vào ngữ cảnh UI hiện tại của Forge (tab txt2img).

    Trả `[]`: các control ở đây chỉ để dựng prompt rồi đổ sang ô của txt2img, nên
    `run()` của Forge không cần nhận giá trị nào từ chúng.
    """
    with gr.Accordion(ACCORDION_LABEL, open=False, elem_id="vi_prompt_accordion"):
        if INDEX is None:
            gr.Markdown("### ❌ Thiếu kho prompt\n\n" + LOST_NOTE)
            return []

        gr.Markdown(
            f"Kho nhắc: **{len(INDEX):,} tag** Danbooru + e621 · "
            f"**{INDEX.stats()['có_nghĩa_tiếng_việt']:,} tag có nghĩa tiếng Việt** · "
            f"biến thể **{ACTIVE_PROFILE_ID or 'fp16'}** "
            f"(CFG {WAI_DEFAULTS['cfg_scale']}, {WAI_DEFAULTS['steps']} bước).\n\n"
            "Gõ tiếng Việt → bấm một dòng để thêm tag → **🪄 Dựng prompt** → "
            "**📋 Đưa vào txt2img** → bấm **Generate** của Forge ngay bên dưới. "
            "Không còn tab riêng và không còn nút sinh ảnh thứ hai."
        )

        # Tag đang chọn để ngoài tabs: bấm thêm ở tab nào cũng thấy ngay kết quả.
        selected = gr.Textbox(label="Tag đã chọn (sửa tay được)", lines=3,
                              elem_id="vi_prompt_selected")
        with gr.Row():
            btn_convert = gr.Button("🔤 Thay mục Việt → tag Anh", scale=2)
            btn_random = gr.Button("🎲 Ngẫu nhiên", scale=1)
            rnd_n = gr.Slider(4, 20, value=8, step=1, label="Số tag", scale=1)
            btn_clear = gr.Button("🗑️ Xoá", scale=1)
        picked = gr.Markdown("", elem_id="vi_prompt_picked")
        state = gr.State([])

        with gr.Tabs(elem_id="vi_prompt_tabs"):
            with gr.Tab("🔎 Tìm & thêm tag", id="vi_prompt_find"):
                query = gr.Textbox(label="Tìm tag (tiếng Việt, không cần gõ dấu)",
                                   placeholder="áo dài, tóc dài, đồng phục học sinh, ao dai…")
                with gr.Row():
                    cats = gr.Dropdown(list(CATEGORY_NAMES.values()),
                                       label="Giới hạn category", multiselect=True, scale=2)
                    limit = gr.Slider(5, 60, value=20, step=5, label="Số kết quả", scale=1)
                allow_nsfw = gr.Checkbox(label="Hiện cả tag 18+", value=False)
                with gr.Row():
                    btn_search = gr.Button("🔎 Tìm", variant="primary", scale=2)
                    group_box = gr.Dropdown([GROUP_LABELS[g] for g in BROWSE_GROUPS],
                                            label="…hoặc duyệt nhóm",
                                            value=GROUP_LABELS[BROWSE_GROUPS[0]], scale=2)
                    btn_browse = gr.Button("📚 Duyệt", scale=1)
                results = gr.Dataframe(
                    headers=["tag", "nghĩa tiếng Việt", "category", "số ảnh", "nhóm"],
                    interactive=False, label="BẤM VÀO MỘT DÒNG để chọn/thay tag")
                note = gr.Markdown("")

            with gr.Tab("🎨 Phong cách", id="vi_prompt_style"):
                with gr.Row():
                    style_group = gr.Dropdown(style_group_choices(),
                                              value=(style_group_choices() or [None])[0],
                                              label="Nhóm phong cách", scale=3)
                    style_preset = gr.Dropdown(style_preset_choices(), value=NO_PRESET,
                                               label="Công thức sẵn (chọn là tick sẵn)",
                                               scale=4)
                style_query = gr.Textbox(label="Tìm trong kho phong cách (không cần dấu)",
                                         placeholder="màu nước, cel, ukiyo-e, ánh sáng viền…")
                style_checked = gr.CheckboxGroup(
                    choices=(STYLES.choices() if style_ready() else []), value=[],
                    label="Tick tag phong cách — đang hiện đủ tag, đổi nhóm để lọc")
                with gr.Row():
                    btn_style_add = gr.Button("➕ Thêm tag phong cách", variant="secondary",
                                              scale=3)
                    btn_style_clear = gr.Button("☐ Bỏ tick", scale=1)
                style_note = gr.Markdown(style_initial_note())
                style_table = gr.Dataframe(headers=STYLE_HEADERS, interactive=False,
                                           label="Độ mạnh của từng tag (theo số bài đăng)")
                with gr.Accordion("📋 12 công thức sẵn — xem tag của từng công thức",
                                  open=False) as style_showcase:
                    gr.Markdown(STYLES.presets_markdown() if style_ready() else "")

            with gr.Tab("🪄 Dựng prompt", id="vi_prompt_build"):
                description = gr.Textbox(
                    label="Câu mô tả tiếng Anh (tuỳ chọn; không tự dịch cả câu)",
                    placeholder="A girl in an ao dai under cherry blossoms")
                with gr.Row():
                    rating = gr.Dropdown(RATING_CHOICES, value=RATING_CHOICES[0],
                                         label="Mức phân loại", scale=2)
                    quality = gr.Dropdown(list(QUALITY_PRESETS), value="Ngắn gọn",
                                          label="Tag chất lượng", scale=2)
                neg_preset = gr.Dropdown(list(NEGATIVE_PRESETS),
                                         value="WAI khuyến nghị (ngắn)",
                                         label="Negative mẫu")
                with gr.Row():
                    artist_prefix = gr.Dropdown(["", "artist:", "@"], value="",
                                                label="Tiền tố hoạ sĩ", scale=1)
                    extra_pos = gr.Textbox(label="Thêm positive", scale=1)
                    extra_neg = gr.Textbox(label="Thêm negative", scale=1)

                btn_build = gr.Button("🪄 Dựng prompt", variant="primary")
                prompt_out = gr.Textbox(label="Positive prompt", lines=4, **COPY_BTN)
                negative_out = gr.Textbox(label="Negative prompt", lines=3, **COPY_BTN)
                build_note = gr.Markdown("")
                group_table = gr.Dataframe(headers=["Nhóm", "Tag"], interactive=False,
                                           label="Cấu trúc prompt")
                vi_preview = gr.Textbox(label="Xem trước tiếng Việt", lines=5)

                # Điền thẳng vào ô txt2img bằng JS (xem javascript/vi_prompt.js)
                with gr.Row():
                    btn_fill = gr.Button("📋 Đưa vào txt2img", variant="secondary", scale=2)
                    btn_undo = gr.Button("↩️ Hoàn tác điền txt2img", scale=1)
                replace_all = gr.Checkbox(
                    label="Thay toàn bộ prompt đích (mặc định chỉ ghép/thay mục trùng)",
                    value=False)
                fill_note = gr.Markdown("", elem_id="vi_prompt_fill_note")

        btn_search.click(do_search, [query, cats, limit, allow_nsfw],
                         [results, state, note])
        query.submit(do_search, [query, cats, limit, allow_nsfw],
                     [results, state, note])
        btn_browse.click(do_browse, [group_box, limit, allow_nsfw],
                         [results, state, note])
        results.select(on_pick, [state, selected], [selected, picked])
        style_outputs = [style_checked, style_table, style_note, style_showcase]
        style_group.change(do_style_group, [style_group, style_query, style_checked],
                           style_outputs, queue=False)
        style_query.change(do_style_group, [style_group, style_query, style_checked],
                           style_outputs, queue=False)
        style_query.submit(do_style_group, [style_group, style_query, style_checked],
                           style_outputs, queue=False)
        style_preset.change(do_style_preset, [style_preset, style_group],
                            [style_checked, style_table, style_note], queue=False)
        btn_style_add.click(do_style_add, [selected, style_checked], [selected, picked])
        btn_style_clear.click(lambda: gr.update(value=[]), None, [style_checked], queue=False)
        btn_convert.click(do_convert, [selected], [selected, picked], queue=False)
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
    return []


class ViPromptInline(Script):
    """Script alwayson: Forge tự dựng khối này trong vùng script của tab txt2img.

    Không đăng ký tab riêng nữa (`script_callbacks.on_ui_tabs` đã bỏ). Forge tự tìm
    lớp con của `Script` trong `scripts/*.py`, nên không cần dòng đăng ký nào.
    """

    def title(self):
        return "Prompt tiếng Việt"

    def show(self, is_img2img):
        # Chỉ txt2img: khối này đổ prompt vào ô Prompt/Negative của txt2img.
        return False if is_img2img else AlwaysVisible

    def ui(self, is_img2img):
        return build_ui()
