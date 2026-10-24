"""Đo và tối ưu **prompt dài** cho SDXL / Illustrious / WAI v17.

Vì sao prompt dài bị "rơi" chi tiết:

* CLIP chỉ đọc **75 token** mỗi cửa sổ (77 gồm BOS/EOS). Prompt 200 token = 3 cửa sổ.
* SDXL có 2 text encoder (CLIP-L 768 chiều + OpenCLIP-bigG 1280 chiều). Forge ghép
  các cửa sổ thành một chuỗi rồi mới cho UNet cross-attend, nên **token càng xa
  đầu prompt càng ít trọng số**: chi tiết nằm ở cửa sổ 3–4 gần như chỉ còn tác
  dụng gợi ý, còn tag ở cửa sổ 1 quyết định bố cục.
* Vì vậy muốn "không bỏ chi tiết" thì phải **giữ tổng độ dài trong ngân sách** và
  **đặt chi tiết quan trọng lên đầu**, chứ không phải viết dài hơn.

Module thuần stdlib, không cần Gradio/GPU. Số token là **ước lượng ±10%** vì repo
không kèm tokenizer CLIP: mỗi mẩu chữ ≤ 7 ký tự ≈ 1 token, dài hơn thì chia thêm;
mỗi dấu `_ ( ) : .` và mỗi dấu phẩy ≈ 1 token.

Dùng:

    from prompt_lib.limits import audit_prompt, compact_prompt
    rep = audit_prompt("masterpiece, 1girl, ...")
    rep["tokens"], rep["windows"], rep["advice"]
    compact_prompt("1girl, blue_eyes, eyes, long_hair")   # -> bỏ "eyes" (trùng nghĩa)
"""

import re

from .editing import split_prompt
from .index import norm

CHUNK_TOKENS = 75          # số token nội dung mỗi cửa sổ CLIP (77 - BOS - EOS)
WINDOW_TOKENS = 77         # cửa sổ CLIP đầy đủ, chỉ để giải thích

# Ngân sách thực dụng: 1 cửa sổ = rất chắc; 2 cửa sổ = còn tốt; 3 cửa sổ = bắt đầu loãng.
BUDGET_OK = CHUNK_TOKENS
BUDGET_GOOD = CHUNK_TOKENS * 2
BUDGET_MAX = CHUNK_TOKENS * 3

_INFRA = re.compile(r"^<(?:lora|lyco|embedding|hypernet):", re.I)
_WORD = re.compile(r"[^\W_]+", re.U)


def tags_of(text):
    """Danh sách mảnh prompt theo thứ tự, đã bỏ mảnh rỗng và BREAK.

    Dùng chung `split_prompt` của `prompt_lib.editing` nên dấu phẩy trong
    `(a, b:1.2)` hay trong `<lora:...>` không bị cắt sai.
    """
    return [piece.strip() for piece in split_prompt(text)
            if piece.strip() and piece.strip() != "BREAK"]


def piece_tokens(piece):
    """Ước lượng số token CLIP của một mảnh (`long_hair`, `(blue_eyes:1.2)`, `<lora:x:0.8>`)."""
    total = 0
    for chunk in str(piece).split():
        for part in re.findall(r"[A-Za-z]+|\d+|[^\sA-Za-z\d]", chunk):
            if part.isdigit():
                total += max(1, -(-len(part) // 3))
            elif part.isalpha():
                total += max(1, -(-len(part) // 7))
            else:
                total += 1
    return total


def estimate_tokens(text):
    """Ước lượng tổng token của prompt (kể cả dấu phẩy phân cách)."""
    pieces = tags_of(text)
    if not pieces:
        return 0
    return sum(piece_tokens(p) for p in pieces) + (len(pieces) - 1)


def window_map(text):
    """Chia prompt thành các cửa sổ CLIP ≤ 75 token (tính cả dấu phẩy).

    Trả về `[{"index": 1, "tokens": n, "tags": [...]}, ...]` để in bảng cho
    người dùng thấy chi tiết nào đang nằm ở cửa sổ nào.
    """
    windows, current, used = [], [], 0
    for piece in tags_of(text):
        cost = piece_tokens(piece) + (1 if current else 0)
        if current and used + cost > CHUNK_TOKENS:
            windows.append({"index": len(windows) + 1, "tokens": used, "tags": current})
            current, used = [], 0
            cost = piece_tokens(piece)
        current.append(piece)
        used += cost
    if current:
        windows.append({"index": len(windows) + 1, "tokens": used, "tags": current})
    return windows


def _words(piece):
    """Từ gốc của một tag, bỏ trọng số/ngoặc/hậu tố LoRA: `(blue_eyes:1.2)` -> ['blue','eyes']."""
    if _INFRA.match(piece):
        return []
    body = re.sub(r"^\(+|\)+$", "", piece.strip())
    body = re.sub(r":\d+(?:\.\d+)?$", "", body)
    return [w.lower() for w in _WORD.findall(body)]


def redundant_pairs(text, group_of=None):
    """Cặp tag trùng nghĩa: tag ngắn nằm trọn trong tag dài (`eyes` ⊂ `blue_eyes`).

    `group_of` (tuỳ chọn) là hàm `tag -> nhóm`; khi truyền vào thì chỉ xếp cặp
    trùng khi **cùng nhóm**, tránh xoá nhầm `sword` khi có `holding_sword`.
    """
    pairs, seen = [], []
    for piece in tags_of(text):
        words = _words(piece)
        if not words or len(words) > 4:
            continue
        seen.append((piece, words))
    for short, short_words in seen:
        for long, long_words in seen:
            if short == long or short_words == long_words:
                continue
            if not set(short_words) <= set(long_words):
                continue
            if len(long_words) <= len(short_words):
                continue
            if group_of is not None:
                try:
                    if group_of(_body(short)) != group_of(_body(long)):
                        continue
                except Exception:
                    pass
            pairs.append((short, long))
            break
    return pairs


def _body(piece):
    body = re.sub(r"^\(+|\)+$", "", piece.strip())
    return re.sub(r":\d+(?:\.\d+)?$", "", body).strip()


def compact_prompt(text, group_of=None, keep=()):
    """Bỏ tag trùng nghĩa + trùng lặp, giữ nguyên thứ tự; không tự bỏ tag riêng biệt.

    `keep` là các tag người dùng muốn giữ bằng mọi giá (so khớp không dấu, không
    phân biệt hoa thường). Trả `(prompt_mới, [tag đã bỏ])`.
    """
    keep_keys = {norm(k) for k in keep if str(k).strip()}
    droppable = {norm(_body(short)) for short, _long in redundant_pairs(text, group_of)}
    out, removed, seen = [], [], set()
    for piece in split_prompt(text):
        stripped = piece.strip()
        if not stripped:
            continue
        if stripped == "BREAK":
            out.append("BREAK")
            continue
        key = norm(_body(stripped))
        if key in seen or (key in droppable and key not in keep_keys):
            removed.append(stripped)
            continue
        seen.add(key)
        out.append(stripped)
    return ", ".join(out), removed


def audit_prompt(text, group_of=None, budget=BUDGET_GOOD):
    """Báo cáo độ dài: token, số cửa sổ, chi tiết nằm muộn, tag trùng nghĩa, lời khuyên.

    Trả dict: `tokens, windows, window_rows, tag_count, level, late_count,
    redundant, advice, budget, within_budget`.
    """
    text = str(text or "")
    pieces = tags_of(text)
    windows = window_map(text)
    tokens = estimate_tokens(text)
    redundant = redundant_pairs(text, group_of)

    # Tag bắt đầu sau cửa sổ 2 gần như chỉ còn "gợi ý": đếm để cảnh báo.
    late, running = [], 0
    for piece in pieces:
        cost = piece_tokens(piece) + 1
        if running >= CHUNK_TOKENS * 2:
            late.append(piece)
        running += cost

    if tokens <= BUDGET_OK:
        level = "gọn (1 cửa sổ)"
    elif tokens <= BUDGET_GOOD:
        level = "vừa (2 cửa sổ)"
    elif tokens <= BUDGET_MAX:
        level = "dài (3 cửa sổ)"
    else:
        level = f"rất dài ({len(windows)} cửa sổ)"

    advice = []
    if not pieces:
        advice.append("Chưa có tag nào để đo.")
    else:
        if tokens <= BUDGET_OK:
            advice.append(f"✅ {tokens} token < {BUDGET_OK}: mọi tag đều nằm trong cửa sổ "
                          "đầu nên model đọc đủ, không rơi chi tiết.")
        elif tokens <= BUDGET_GOOD:
            advice.append(f"🟡 {tokens} token: còn ổn nhưng chi tiết ở nửa sau đã yếu hơn. "
                          "Đưa chi tiết bắt buộc lên đầu, tag trang trí (hoạ sĩ, meta, "
                          "phong cách) xuống cuối.")
        else:
            advice.append(f"🔴 {tokens} token ≥ 3 cửa sổ: tag ở cửa sổ 3 trở đi hầu như "
                          "không còn tác dụng. Nên cắt về ≤ 150 token hoặc chia 2 lượt "
                          "(xem PROMPT_DAI.md).")
        if late:
            advice.append(f"⚠️ **{len(late)}** tag nằm sau token {CHUNK_TOKENS * 2} "
                          f"(bị loãng): " + ", ".join(f"`{t}`" for t in late[:6])
                          + (" …" if len(late) > 6 else ""))
        if redundant:
            advice.append("♻️ Trùng nghĩa, bỏ được: " + ", ".join(
                f"`{short}` (đã có `{long}`)" for short, long in redundant[:6]))
        if len(windows) > 1:
            advice.append("💡 Bật **Chèn BREAK giữa các nhóm** để mỗi nhóm vào một cửa sổ "
                          "riêng, và giữ 1–3 tag quan trọng nhất ở đầu prompt.")
        if tokens > budget:
            advice.append(f"✂️ Ngân sách đang đặt {budget} token — bấm **Nén** để bỏ tag "
                          "trùng nghĩa, hoặc chuyển bớt chi tiết sang lượt img2img.")

    rows = [[f"#{w['index']} (≤{CHUNK_TOKENS} token)", w["tokens"], ", ".join(w["tags"])]
            for w in windows]
    return {
        "tokens": tokens,
        "windows": len(windows),
        "window_rows": rows,
        "tag_count": len(pieces),
        "level": level,
        "late_count": len(late),
        "late": late,
        "redundant": redundant,
        "advice": advice,
        "budget": budget,
        "within_budget": tokens <= budget,
    }


def summary_line(report):
    """Một dòng gọn để dán vào ghi chú của app: '312 token · 5 cửa sổ · 41 tag'."""
    return (f"{report['tokens']} token · {report['windows']} cửa sổ "
            f"{CHUNK_TOKENS} token · {report['tag_count']} tag")
