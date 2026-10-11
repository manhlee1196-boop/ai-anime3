"""Sửa tag không phá mục khác: Việt → Anh, trọng số, LoRA và chuỗi chưa biết."""
import re
import unicodedata

from .index import norm, unaccent

WEIGHT = re.compile(r"^(.+?):(\d+(?:\.\d+)?|\.\d+)$", re.S)


def split_prompt(text):
    """Giữ nguyên từng đoạn; dấu phẩy bên trong ()/[]/<> không phải phân cách."""
    text = str(text or "")
    parts, start, stack = [], 0, []
    pairs = {"(": ")", "[": "]", "<": ">"}
    escaped = False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "<" and not re.match(r"<(?:lora|lyco|embedding|hypernet):", text[i:], re.I):
            continue  # <_< / <3 là emoticon, không mở vùng extra-network
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif char == "," and not stack:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def piece_body(piece):
    """(body, prefix, suffix); giữ nguyên vỏ trọng số/emphasis, kể cả khoảng trắng.

    Không tháo cú pháp LoRA/wildcard/schedule. prefix/suffix không bao gồm
    khoảng trắng ngoài cùng của piece (rewrite_piece giữ riêng phần đó).
    """
    value = piece.strip()
    if not value or value == "BREAK" or value.startswith(("<", "__", "[")):
        return value, "", ""
    start, end, weighted = 0, len(value), False
    while start < end:
        while start < end and value[start].isspace():
            start += 1
        while end > start and value[end - 1].isspace():
            end -= 1
        if value[start:end].startswith("(") and value[end - 1:end] == ")":
            start += 1
            end -= 1
            continue
        match = None if weighted else WEIGHT.fullmatch(value[start:end])
        # 16:9/:3 và các tag giống tỉ lệ chỉ được tách khi có () bao quanh.
        if match and (start or not match[1].strip().isdigit()):
            end = start + len(match[1])
            weighted = True
            continue
        break
    return value[start:end], value[:start], value[end:]


def rewrite_piece(piece, body):
    _, prefix, suffix = piece_body(piece)
    leading = piece[:len(piece) - len(piece.lstrip())]
    trailing = piece[len(piece.rstrip()):]
    return leading + prefix + body + suffix + trailing


def matching_tag(body, tag, index):
    """Kết quả người dùng chọn quyết định ý nghĩa; không tự lấy fuzzy hit khác."""
    if body.startswith(("<", "__", "[")) or body == "BREAK":
        return False
    raw = unicodedata.normalize("NFC", body.strip().casefold())
    literal = raw.replace(" ", "_")
    if raw == tag.casefold() or literal == tag.casefold():
        return True
    # 'hat' là mũ, không phải 'hát'; tên/tag Anh có sẵn không bị đổi nghĩa.
    if index.info_of(literal) or index.info_of(raw):
        return index.exact_tag(body) == index.exact_tag(tag)
    meaning = index.vi_of(tag)
    # Chọn kết quả cụ thể có thể phân biệt bản không dấu; bản có dấu phải khớp dấu.
    if meaning:
        if unaccent(raw) != raw:
            return raw == unicodedata.normalize("NFC", meaning.strip().casefold())
        if norm(body) == norm(meaning):
            return True
    return index.exact_tag(body) == tag


def _identity(tag, prefix, suffix):
    # Khoảng trắng quanh body không thay đổi trọng số, nhưng khác emphasis/weight
    # vẫn là hai mục khác nhau. Không gộp :1.2 và :1.3 hay () và (():...).
    return tag, "".join(prefix.split()), "".join(suffix.split())


def replace_or_append(selected, tag, index):
    """Chọn ao_dai khi đã gõ áo dài → thay tại chỗ, không nối áo dài, ao_dai."""
    parts = split_prompt(selected)
    matched = False
    for i, piece in enumerate(parts):
        body, _, _ = piece_body(piece)
        if matching_tag(body, tag, index):
            parts[i] = rewrite_piece(piece, tag)
            matched = True
    if matched:
        # Chỉ bỏ bản target trùng hệt trọng số, không khử trùng các mục khác.
        seen, kept = set(), []
        for piece in parts:
            body, prefix, suffix = piece_body(piece)
            if body == tag:
                identity = _identity(body, prefix, suffix)
                if identity in seen:
                    continue
                seen.add(identity)
            kept.append(piece)
        return ",".join(kept)
    text = str(selected or "")
    if not text.strip():
        return tag
    return text.rstrip() + (" " if text.rstrip().endswith(",") else ", ") + tag


def convert_tags(text, index):
    """Đổi exact match, bỏ trùng đúng mục đã đổi; giữ unknown/cú pháp/mục khác."""
    parts, changed, unknown, targets = split_prompt(text), [], [], set()
    for i, piece in enumerate(parts):
        body, prefix, suffix = piece_body(piece)
        if not body or body == "BREAK" or body.startswith(("<", "__", "[")):
            continue
        tag = index.exact_tag(body)
        if tag:
            if body != tag:
                parts[i] = rewrite_piece(piece, tag)
                changed.append((body, tag))
                targets.add(_identity(tag, prefix, suffix))
        else:
            unknown.append(body)
    seen, kept = set(), []
    for piece in parts:
        body, prefix, suffix = piece_body(piece)
        identity = _identity(body, prefix, suffix)
        if identity in targets:
            if identity in seen:
                continue
            seen.add(identity)
        kept.append(piece)
    return ",".join(kept), changed, unknown
