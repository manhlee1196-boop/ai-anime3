# -*- coding: utf-8 -*-
"""Bộ ghép bản dịch đệ quy cho tag tổ hợp chưa có trong từ điển.

Thứ tự thử:
  1. từ điển / quy tắc mẫu (do build_vi.py và vi_rules.py xử lý trước)
  2. hậu tố ngoặc phân biệt nghĩa      `sword_(object)`  -> "kiếm (vật thể)"
  3. động từ -ing đứng đầu             `holding_sword`   -> "cầm kiếm"
  4. giới từ nối hai vế               `hand_on_head`    -> "bàn tay trên đầu"
  5. bổ nghĩa + danh từ trung tâm      `school_uniform`  -> "đồng phục trường học"

Nguyên tắc: mọi mảnh ghép đều phải tra được trong từ điển hoặc từ vựng. Mảnh nào
không tra được thì trả về None để tầng build giữ nguyên tag tiếng Anh.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dict"))

from vi_morphemes import COLORS, NUMBERS, SIZES  # noqa: E402
from vi_vocab import (  # noqa: E402
    ADJS,
    NOUNS,
    PREMOD,
    PREPS,
    QUALS,
    SUFS,
    VERBS,
    VOCAB,
)

# từ vựng nền ưu tiên thấp nhất: bảng màu, kích thước, số đếm của vi_morphemes
BASE_VOCAB = {}
for _d in (SIZES, COLORS, NUMBERS):
    for _k, _v in _d.items():
        BASE_VOCAB.setdefault(_k, _v)

RE_PAREN = re.compile(r"^(.+)_\((.+)\)$")

MAX_DEPTH = 6

# giới từ đủ rõ nghĩa để tách vế; bỏ các từ mơ hồ (back, up, down, out, off...)
SAFE_PREPS = {
    "on": "trên", "in": "trong", "inside": "bên trong", "into": "vào trong",
    "under": "dưới", "underneath": "dưới", "beneath": "dưới",
    "over": "phủ lên", "above": "phía trên", "below": "phía dưới",
    "between": "giữa", "among": "giữa", "around": "quanh",
    "through": "xuyên qua", "across": "vắt ngang", "along": "dọc theo",
    "from": "từ", "to": "về phía", "toward": "về phía", "towards": "về phía",
    "at": "vào", "of": "của", "with": "với", "without": "không có",
    "by": "bởi", "against": "dựa vào", "behind": "phía sau",
    "before": "trước", "after": "sau", "during": "trong lúc", "while": "trong khi",
    "beside": "bên cạnh", "onto": "lên trên", "upon": "trên", "within": "bên trong",
    "outside": "bên ngoài",
}

# giới từ ghép nhiều chữ - phải thử TRƯỚC giới từ một chữ (out_of_frame chứ không
# phải tách ở chữ "of")
MULTIPREPS = {
    "on_top_of": "trên",
    "out_of": "ra ngoài",
    "next_to": "bên cạnh",
    "in_front_of": "trước",
    "back_of": "phía sau",
    "top_of": "trên đỉnh",
    "bottom_of": "dưới đáy",
    "middle_of": "giữa",
    "end_of": "cuối",
    "front_of": "trước",
    "side_of": "bên",
    "pair_of": "đôi",
    "lot_of": "nhiều",
    "kind_of": "loại",
    "type_of": "loại",
    "piece_of": "mảnh",
    "cup_of": "cốc",
    "glass_of": "ly",
    "bottle_of": "chai",
    "box_of": "hộp",
    "bag_of": "túi",
    "handful_of": "một nắm",
    "instead_of": "thay vì",
    "because_of": "vì",
    "regardless_of": "bất kể",
    "ahead_of": "phía trước",
    "along_with": "cùng với",
    "together_with": "cùng với",
    "as_well_as": "cũng như",
}

# Từ chỉ TRẠNG THÁI / tính từ: tuy nằm trong bảng VERBS nhưng không được ghép theo
# kiểu động từ đứng đầu, vì tiếng Việt đặt chúng SAU danh từ
# (`messy_bed` = "giường rối bời", không phải "rối bời giường").
STATIVE = {
    "wavy", "curly", "straight", "messy", "slicked_back", "wet", "glowing",
    "shining", "sparkling", "floating", "hovering", "hanging", "suspended",
    "dangling", "attached", "detached", "connected", "merged", "melting",
    "burning", "freezing", "exploding", "shattering", "bleeding", "crying",
    "laughing", "smiling", "grinning", "frowning", "scowling", "blushing",
    "embarrassed", "angry", "sad", "happy", "surprised", "shocked", "scared",
    "worried", "bored", "sleepy", "yawning", "sneezing", "burping", "vomiting",
    "panting", "gasping", "breathing", "raised", "lowered", "arched", "bent",
    "crossed", "folded", "tucked", "draped", "tangled", "braided", "spread",
    "sitting", "standing", "lying", "kneeling", "crouching", "leaning",
    "walking", "running", "jumping", "falling", "swimming", "sleeping",
    "eating", "drinking", "reading", "writing", "drawing", "painting",
    "singing", "dancing", "smoking", "cooking", "fighting", "shooting",
    "stabbing", "slashing", "cutting", "breaking", "throwing", "catching",
    "pushing", "dragging", "climbing", "descending", "ascending", "arriving",
    "leaving", "traveling", "wandering", "hiding", "watching", "staring",
    "glaring", "winking", "talking", "speaking", "shouting", "yelling",
    "screaming", "whispering", "murmuring", "sighing", "giggling",
    "snickering", "peeing", "pooping", "defecating", "urinating", "wetting",
    "soiling", "farting", "orgasm", "orgasming", "cumming", "ejaculating",
    "lactating", "hatching", "rest", "resting", "tickled", "teasing",
    "bullying", "comforting", "protecting", "rescuing", "chasing", "escaping",
    "peeking", "moaning", "sweating", "cuddling", "bouncing", "rolling",
    "flashing", "struggling", "thinking", "stuck", "planted", "constricted",
    "clasped", "slicked", "darkened", "knotted", "chained", "tilted",
    "twitching", "blinking", "penetrated", "implied", "glowing_genitalia",
    "torn", "removed", "exposed", "covered", "obscured", "hidden", "visible",
    "grinding", "thrusting", "pounding", "swallowing", "biting", "chewing",
    "kissing", "hugging", "licking", "sucking", "spanking", "whipping",
    "dripping", "steaming", "soaking", "spraying", "pouring", "spilling",
    "melting", "freezing", "drying", "washing", "bathing", "showering",
    "stretching", "meditating", "praying", "transforming", "evolving",
    "growing", "shrinking", "healing", "training", "exercising",
}

# Động từ có thể đứng GIỮA tag theo mẫu chủ - vị - tân:
#   `female_rimming_male` = "nữ giới quan hệ bằng miệng ở hậu môn nam giới"
# Không đảo trật tự như bổ nghĩa + danh từ.
ACTION_MID = {
    "rimming", "licking", "kissing", "biting", "hugging", "touching",
    "grabbing", "holding", "penetrating", "fondling", "groping", "slapping",
    "spanking", "whipping", "tickling", "sucking", "fellatio", "cunnilingus",
    "handjob", "fingering", "masturbation", "sex", "vore", "pred", "play",
    "worship", "chasing", "watching", "following", "carrying", "riding",
    "driving", "pulling", "pushing", "lifting", "grab", "pull", "lick",
    "poke", "poking", "tweak", "pinch", "pinching", "tug", "tugging",
    "rubbing", "blowing", "turning", "facing", "milking", "flexing",
    "adjusting", "covering", "carrying_another", "carrying_person",
    "penetrated", "grinding", "thrusting", "pounding", "wetting", "soiling",
    "feeding", "worshipping", "tickling", "teasing", "bullying",
}

# động từ "wearing" cần chọn động từ tiếng Việt theo loại trang phục
WEAR_VERB = [
    (("mũ", "nón", "vương miện", "băng đô", "khăn trùm đầu", "đồ đội đầu"), "đội"),
    (("kính", "bịt mắt"), "đeo"),
    (("giày", "dép", "tất", "găng", "ủng", "guốc"), "mang"),
    (("vòng", "nhẫn", "khuyên", "trang sức", "trâm", "dây chuyền"), "đeo"),
]


def _join_dedup(a, b):
    """Ghép "{a} {b}" nhưng bỏ từ bị lặp ngay chỗ nối.

    Ví dụ deer_antlers: a="gạc hươu", b="hươu" -> "gạc hươu" (không phải "gạc hươu hươu").
    rose_petals: a="cánh hoa", b="hoa hồng" -> "cánh hoa hồng".
    """
    if not a:
        return b
    if not b:
        return a
    aw, bw = a.split(), b.split()
    if b in a.split() or " ".join(bw) == " ".join(aw):
        return a
    if aw[-1] == bw[0]:
        rest = bw[1:]
        return a if not rest else a + " " + " ".join(rest)
    # b nằm trọn trong a -> giữ a
    if len(bw) > 1 and " ".join(bw) in a:
        return a
    # a chính là từ cuối của b ("boat" + "sailing boat") -> giữ b
    if len(aw) == 1 and bw[-1] == aw[0]:
        return b
    return a + " " + b


def _plural_fallback(word, lookup):
    """Thử dạng số ít / số nhiều khi từ không có nguyên trạng."""
    for cand in (word[:-1], word + "s", word[:-2] if word.endswith("es") else None,
                 word.replace("_", "-"), word.replace("-", "_")):
        if cand and cand != word:
            v = lookup(cand)
            if v:
                return v
    return None


class Composer:
    def __init__(self, dict_lookup):
        """dict_lookup: hàm tra từ điển chính (MERGED của build_vi)."""
        self.dict = dict_lookup
        self.cache = {}

    # -- tra cứu một mảnh ---------------------------------------------------
    def word(self, w):
        if not w:
            return None
        v = self.dict(w)
        if v:
            return v
        v = VOCAB.get(w) or BASE_VOCAB.get(w)
        if v:
            return v
        return (_plural_fallback(w, self.dict)
                or _plural_fallback(w, VOCAB.get)
                or _plural_fallback(w, BASE_VOCAB.get))

    # -- dịch cả cụm token --------------------------------------------------
    def phrase(self, tokens, depth=0):
        if not tokens or depth > MAX_DEPTH:
            return None
        s = "_".join(tokens)
        if s in self.cache:
            return self.cache[s]
        result = self._phrase(tokens, depth)
        self.cache[s] = result
        return result

    def _phrase(self, tokens, depth):
        s = "_".join(tokens)
        # tra nguyên cụm trước (từ điển chính rồi tới từ vựng)
        v = self.dict(s) or VOCAB.get(s) or BASE_VOCAB.get(s)
        if v:
            return v

        if len(tokens) == 1:
            return self.word(tokens[0])

        # 1) động từ -ing đứng đầu: "holding sword" -> "cầm kiếm"
        head = tokens[0]
        if head in VERBS and head not in STATIVE:
            rest = self.phrase(tokens[1:], depth + 1)
            if rest:
                # khử trùng lặp chỗ nối: "sailing"="chèo thuyền" + "boat"="thuyền"
                out = _join_dedup(VERBS[head], rest)
                if head == "wearing":
                    for keys, verb in WEAR_VERB:
                        if any(k in rest for k in keys):
                            out = _join_dedup(verb, rest)
                            break
                return out

        # 2) lượng từ đứng đầu: "multiple girls" -> "nhiều cô gái"
        if head in PREMOD:
            rest = self.phrase(tokens[1:], depth + 1)
            if rest:
                return _join_dedup(PREMOD[head], rest)

        # 3) giới từ ghép nhiều chữ: thử cụm 3 chữ rồi 2 chữ
        #    "head out_of frame" -> "đầu ra ngoài khung hình"
        #    "in_front_of mirror" -> "trước gương"
        for width in (3, 2):
            for i in range(0, len(tokens) - width + 1):
                pm = "_".join(tokens[i:i + width])
                if pm not in MULTIPREPS:
                    continue
                left = self.phrase(tokens[:i], depth + 1) if i else None
                right = self.phrase(tokens[i + width:], depth + 1)
                if not right:
                    continue
                if left:
                    return "{} {} {}".format(left, MULTIPREPS[pm], right)
                if i == 0:
                    return "{} {}".format(MULTIPREPS[pm], right)

        # 4) giới từ một chữ nối hai vế: "hand on head" -> "bàn tay trên đầu"
        for i in range(0, len(tokens) - 1):
            p = tokens[i]
            if p in SAFE_PREPS:
                left = self.phrase(tokens[:i], depth + 1) if i else None
                right = self.phrase(tokens[i + 1:], depth + 1)
                if right and (left or i == 0):
                    if left:
                        return "{} {} {}".format(left, SAFE_PREPS[p], right)
                    return "{} {}".format(SAFE_PREPS[p], right)

        # 5) hậu tố: "panties removed" -> "quần lót đã tháo ra"
        last = tokens[-1]
        if last in SUFS and len(tokens) > 1:
            rest = self.phrase(tokens[:-1], depth + 1)
            if rest:
                return "{} {}".format(rest, SUFS[last])

        # 6) chủ - vị - tân: "female rimming male" -> giữ nguyên trật tự
        for i in range(1, len(tokens) - 1):
            mid = tokens[i]
            if mid in ACTION_MID or (mid in VERBS and mid not in STATIVE):
                left = self.phrase(tokens[:i], depth + 1)
                right = self.phrase(tokens[i + 1:], depth + 1)
                mid_vi = VERBS.get(mid) or self.dict(mid) or VOCAB.get(mid)
                if left and right and mid_vi:
                    return "{} {} {}".format(left, mid_vi, right)

        # 7) bổ nghĩa + danh từ trung tâm: "school uniform" -> "đồng phục trường học"
        #    ưu tiên tách phần bổ nghĩa DÀI nhất (ghép tham lam) để giữ cụm từ liền nhau
        for i in reversed(range(1, len(tokens))):
            pre = self.phrase(tokens[:i], depth + 1)
            suf = self.phrase(tokens[i:], depth + 1)
            if pre and suf:
                return _join_dedup(suf, pre)

        return None

    # -- điểm vào chính ------------------------------------------------------
    def translate(self, tag):
        if tag in self.cache:
            return self.cache[tag]
        out = self._translate(tag)
        self.cache[tag] = out
        return out

    def _translate(self, tag):
        # hậu tố ngoặc phân biệt nghĩa
        m = RE_PAREN.match(tag)
        if m:
            base, qual = m.group(1), m.group(2)
            qual_vi = QUALS.get(qual)
            base_vi = (self.dict(base) or VOCAB.get(base) or BASE_VOCAB.get(base)
                       or self.phrase(base.split("_")))
            if qual_vi:
                if base_vi:
                    if qual_vi in base_vi:
                        return base_vi
                    return "{} ({})".format(base_vi, qual_vi)
                # tên riêng không dịch được: giữ nguyên, chỉ dịch phần ngoặc
                return "{} ({})".format(base.replace("_", " "), qual_vi)
            if base_vi:
                return "{} ({})".format(base_vi, qual.replace("_", " "))
            return None

        return self.phrase(tag.split("_"))
