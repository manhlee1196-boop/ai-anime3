"""Ghép prompt: nhận tag đã chọn -> chuỗi prompt tiếng Anh đúng thứ tự Illustrious/WAI.

Cũng dựng negative prompt, payload cho API của Forge, và bản xem trước tiếng Việt.
"""

import csv
import io
import re

from . import groups as G
from .system_tags import (NEGATIVE_PRESETS, QUALITY_PRESETS, RATINGS, SIZE_PRESETS,
                          WAI_DEFAULTS, pick_upscaler)

LORA_RE = re.compile(r"^<(lora|lyco|embedding|hypernet):")
WEIGHT_RE = re.compile(r"^(?P<body>.+?):(?P<w>\d+\.\d+|\d+)$")

RATING_BY_ID = {r["id"]: r for r in RATINGS}


def parse_pieces(text, index=None):
    """Tách chuỗi tag người dùng nhập thành danh sách (tag, weight).

    - Chấp nhận cả `tag:1.2` và `(tag:1.2)`.
    - Không nhầm `16:9`, `:3`, `9/11` với cú pháp trọng số.
    - `<lora:...>` / `<embedding:...>` được giữ nguyên ở cuối prompt.
    - Nếu một mảnh không phải tag đã biết mà là tiếng Việt thì thử tra ngược.
    """
    pieces, specials, unresolved = [], [], []
    for chunk in str(text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if LORA_RE.match(chunk):
            specials.append((chunk, None))
            continue

        weight = None
        body = chunk
        if body.startswith("(") and body.endswith(")"):
            inner = body[1:-1]
            m = WEIGHT_RE.match(inner)
            if m:
                body, weight = m.group("body").strip(), _as_weight(m.group("w"))
        else:
            m = WEIGHT_RE.match(body)
            if m and index is not None:
                cand = m.group("body").strip()
                # chỉ coi là trọng số nếu phần còn lại đúng là một tag đã biết
                if index.info_of(cand) or index.info_of(cand.replace(" ", "_")):
                    body, weight = cand, _as_weight(m.group("w"))

        key = body.strip()
        if not key:
            continue
        tag = _resolve(key, index)
        if tag:
            pieces.append((tag, weight))
        else:
            unresolved.append(key)
            pieces.append((key.replace(" ", "_"), weight))
    return pieces, specials, unresolved


def _as_weight(text):
    try:
        value = float(text)
    except ValueError:
        return None
    return value if 0.0 <= value <= 5.0 else None


def _resolve(key, index):
    """Trả về tag tiếng Anh đúng chuẩn nếu tra được, ngược lại None."""
    if index is None:
        return None
    underscored = key.replace(" ", "_")
    if index.info_of(underscored):
        return underscored
    if index.info_of(key):
        return key
    hits = index.search(key, limit=1)
    if hits and hits[0].score >= 900:     # chỉ nhận khớp chắc chắn
        return hits[0].tag
    return None


def render(tag, weight=None):
    """Viết tag ra dạng prompt, kèm trọng số nếu có."""
    if weight is None:
        return tag
    return f"({tag}:{weight:g})"


class PromptBuilder:
    def __init__(self, index):
        self.index = index

    # ------------------------------------------------------------------ phân nhóm
    def bucket(self, pieces):
        buckets = {g: [] for g in G.GROUP_ORDER}
        for tag, weight in pieces:
            group = self.index.group_of(tag)
            buckets.setdefault(group, []).append((tag, weight))
        return buckets

    # ------------------------------------------------------------------ ghép prompt
    def assemble(self, selected, description="", rating_id="general",
                 quality_preset="WAI khuyến nghị (đầy đủ)", extra_positive="",
                 artist_prefix="", use_break=False, drop_duplicates=True):
        """Trả về dict chứa prompt tiếng Anh + bản xem trước tiếng Việt."""
        pieces, specials, unresolved = parse_pieces(selected, self.index)
        buckets = self.bucket(pieces)

        rating = RATING_BY_ID.get(rating_id, RATINGS[0])
        quality = QUALITY_PRESETS.get(quality_preset, "")

        ordered, seen = [], set()

        def push(tags):
            for tag in tags:
                if not tag:
                    continue
                key = tag.strip().lower()
                if drop_duplicates and key in seen:
                    continue
                seen.add(key)
                ordered.append(tag.strip())

        # tag chất lượng & phân loại luôn đi đầu (quy ước NoobAI/Illustrious)
        push(_split(quality))
        push(rating["positive"])

        for group in G.GROUP_ORDER:
            if group in ("quality", "rating"):
                continue
            items = buckets.get(group) or []
            if not items:
                continue
            if group == "artist" and artist_prefix:
                items = [(f"{artist_prefix}{t}", w) for t, w in items]
            push(render(t, w) for t, w in items)
            if use_break:
                ordered.append("BREAK")

        push(_split(extra_positive))
        push(t for t, _ in specials)

        description = (description or "").strip()
        prompt_parts = []
        if description:
            prompt_parts.append(description.rstrip(".,"))
        body = ", ".join(p for p in ordered if p)
        if body:
            prompt_parts.append(body)
        prompt = ", ".join(prompt_parts)

        return {
            "prompt": prompt,
            "negative": self.negative(rating_id),
            "groups": {g: [t for t, _ in (buckets.get(g) or [])]
                       for g in G.GROUP_ORDER if buckets.get(g)},
            "vi_preview": self.vi_preview(ordered, description, rating_id),
            "unresolved": unresolved,
            "count": len([p for p in ordered if p and p != "BREAK"]),
        }

    # ------------------------------------------------------------------ negative
    def negative(self, rating_id="general", preset="Chuẩn cộng đồng (đầy đủ)",
                 extra_negative=""):
        rating = RATING_BY_ID.get(rating_id, RATINGS[0])
        parts = [NEGATIVE_PRESETS.get(preset, "")]
        # mức phân loại không chọn -> đẩy sang negative (đúng hướng dẫn của thẻ model)
        parts.append(", ".join(rating["negative"]))
        if extra_negative:
            parts.append(extra_negative)
        joined = ", ".join(p for p in parts if p and p.strip())
        # khử trùng lặp, giữ thứ tự
        seen, out = set(), []
        for piece in joined.split(","):
            key = piece.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(piece.strip())
        return ", ".join(out)

    # ------------------------------------------------------------------ xem trước
    def vi_preview(self, ordered, description, rating_id):
        """Bản tiếng Việt của prompt để người dùng biết mình đang tạo gì."""
        lines = []
        if description:
            lines.append(f"Mô tả: {description}")
        rating = RATING_BY_ID.get(rating_id, RATINGS[0])
        lines.append(f"Phân loại: {rating['label']}")
        by_group = {}
        for piece in ordered:
            if piece == "BREAK":
                continue
            tag = re.sub(r"^\(|:\d+(?:\.\d+)?\)$", "", piece).strip()
            vi = self.index.vi_of(tag)
            if not vi:
                continue
            by_group.setdefault(self.index.group_of(tag), []).append(vi)
        for group in G.GROUP_ORDER:
            items = by_group.get(group)
            if items:
                lines.append(f"{G.GROUP_LABELS.get(group, group)}: " + ", ".join(items))
        return "\n".join(lines)

    # ------------------------------------------------------------------ tham số
    def payload(self, prompt, negative, overrides=None):
        """Body cho POST /sdapi/v1/txt2img của Forge."""
        body = dict(WAI_DEFAULTS)
        body.update({"prompt": prompt, "negative_prompt": negative})
        for key, value in (overrides or {}).items():
            if value is None:
                continue
            body[key] = value
        # Neo API nhận sampler và scheduler riêng; giữ lựa chọn UI cũ nhưng
        # không gửi "DPM++ 2M Karras" như một tên sampler không tồn tại.
        combined = {"DPM++ 2M Karras": "DPM++ 2M", "DPM++ 2M SDE Karras": "DPM++ 2M SDE"}
        if body.get("sampler_name") in combined:
            body["sampler_name"] = combined[body["sampler_name"]]
            if not (overrides or {}).get("scheduler"):
                body["scheduler"] = "Karras"
        if not body.get("enable_hr"):
            for key in ("hr_upscaler", "hr_scale", "hr_second_pass_steps",
                        "denoising_strength"):
                body.pop(key, None)
        return body

    @staticmethod
    def fix_upscaler(payload, available):
        """Sửa `hr_upscaler` cho khớp với danh sách upscaler backend đang có."""
        if payload.get("enable_hr") and payload.get("hr_upscaler"):
            chosen = pick_upscaler(available or [], payload["hr_upscaler"])
            payload["hr_upscaler"] = chosen
        return payload

    def apply_size(self, overrides, size_preset):
        size = SIZE_PRESETS.get(size_preset)
        if size:
            overrides["width"], overrides["height"] = size
        return overrides

    # ------------------------------------------------------------------ styles.csv
    def styles_csv(self):
        """Sinh nội dung styles.csv cho Forge (mỗi preset là một Style bấm được)."""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["name", "prompt", "negative_prompt"])
        for rating in RATINGS:
            name = f"WAI v17 — {rating['label']}"
            positive = ", ".join(
                [QUALITY_PRESETS["WAI khuyến nghị (đầy đủ)"]] + rating["positive"])
            writer.writerow([name, positive,
                             self.negative(rating["id"], "Chuẩn cộng đồng (đầy đủ)")])
        return buf.getvalue()


def _split(text):
    return [p.strip() for p in str(text or "").split(",") if p.strip()]
