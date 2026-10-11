"""Mục lục tra cứu hai chiều Việt <-> Anh cho kho prompt Danbooru + e621.

Nạp từ chính các file CSV đã build ở thư mục gốc repo:
- `danbooru_e621.csv`              : tag, category, post_count, aliases (bản gốc)
- `danbooru_e621_vi_translation.csv`: tag gốc, bản dịch tiếng Việt (45.443 dòng)
- `system_tags.SYSTEM_TAGS`        : tag hệ thống Illustrious/WAI không có trong CSV

Tìm kiếm không phân biệt dấu tiếng Việt ("ao dai" vẫn ra "áo dài").
"""

import bisect
import csv
import os
import unicodedata
from collections import defaultdict

from . import groups as G
from .system_tags import SYSTEM_TAGS

CSV_FILES = ("danbooru_e621.csv", "danbooru_e621_vi_translation.csv")

# Tên category trong file merged, hiển thị bằng tiếng Việt
CATEGORY_NAMES = {
    0: "Chung (Danbooru)",
    1: "Nghệ sĩ (Danbooru)",
    3: "Series (Danbooru)",
    4: "Nhân vật (Danbooru)",
    5: "Meta (Danbooru)",
    7: "Chung (e621)",
    8: "Nghệ sĩ (e621)",
    9: "Series (e621)",
    10: "Nhân vật (e621)",
    11: "Đóng góp (e621)",
    12: "Loài (e621)",
    14: "Meta (e621)",
    15: "Cốt truyện (e621)",
}


def unaccent(text):
    """Bỏ dấu tiếng Việt: 'áo dài' -> 'ao dai'."""
    nfkd = unicodedata.normalize("NFD", text)
    out = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return out.replace("đ", "d").replace("Đ", "D")


def norm(text):
    """Chuẩn hoá để so khớp: chữ thường, bỏ dấu, '_' -> khoảng trắng, gộp khoảng trắng."""
    t = unaccent(str(text).strip().lower()).replace("_", " ")
    return " ".join(t.split())


def find_repo_root(start=None):
    """Tìm thư mục chứa các file CSV của kho prompt."""
    here = os.path.abspath(start or os.path.dirname(__file__))
    for _ in range(6):
        if all(os.path.exists(os.path.join(here, f)) for f in CSV_FILES):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return None


class TagResult:
    """Một kết quả tra cứu."""

    __slots__ = ("tag", "vi", "category", "post_count", "group", "score")

    def __init__(self, tag, vi, category, post_count, group, score=0):
        self.tag = tag
        self.vi = vi
        self.category = category
        self.post_count = post_count
        self.group = group
        self.score = score

    def as_row(self):
        return (
            self.tag,
            self.vi or f"{self.tag.replace('_', ' ')} (từ mượn, giữ nguyên)",
            CATEGORY_NAMES.get(self.category, "Hệ thống"),
            f"{self.post_count:,}",
            G.GROUP_LABELS.get(self.group, self.group),
        )

    def __repr__(self):
        return f"<Tag {self.tag!r} = {self.vi!r} pc={self.post_count}>"


class TagIndex:
    """Mục lục tra cứu; `load()` tách riêng để app khởi động nhanh."""

    def __init__(self, root=None, autoload=True):
        self.root = root or find_repo_root()
        self.loaded = False
        self._info = {}          # tag -> (category, post_count)
        self._vi = {}            # tag -> bản dịch tiếng Việt
        self._sys_group = {}     # tag hệ thống -> nhóm
        self._vi_items = []      # [(norm_vi, tag)] cho tìm kiếm tiếng Việt
        self._en_keys = []       # [(norm_tag, tag)] đã sắp xếp cho bisect
        self._alias = {}         # norm(alias) -> tag
        self._by_count = []      # [tag] sắp theo post_count giảm dần
        self._group_cache = {}
        if autoload and self.root:
            self.load()

    # ------------------------------------------------------------------ nạp dữ liệu
    def load(self):
        if not self.root:
            raise FileNotFoundError(
                "Không tìm thấy " + " và ".join(CSV_FILES) +
                " — hãy truyền tham số root=<thư mục repo>.")
        main_csv = os.path.join(self.root, CSV_FILES[0])
        trans_csv = os.path.join(self.root, CSV_FILES[1])

        with open(main_csv, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) < 3:
                    continue
                tag, cat, pc = row[0], row[1], row[2]
                try:
                    self._info[tag] = (int(cat), int(pc))
                except ValueError:
                    continue
                if len(row) >= 4 and row[3]:
                    for alias in row[3].split(","):
                        alias = alias.strip()
                        if alias and alias != tag:
                            self._alias.setdefault(norm(alias), tag)

        if os.path.exists(trans_csv):
            with open(trans_csv, newline="", encoding="utf-8") as f:
                for row in csv.reader(f):
                    if len(row) >= 2 and row[1].strip():
                        self._vi[row[0]] = row[1]

        # tag hệ thống Illustrious/WAI (không có trong CSV)
        for tag, (vi, group) in SYSTEM_TAGS.items():
            self._sys_group[tag] = group
            if tag not in self._vi:
                self._vi[tag] = vi
            if tag not in self._info:
                # category 5 = Meta, để tagcomplete xếp màu đúng
                self._info[tag] = (5, 0)

        # chỉ mục tìm kiếm
        self._vi_items = [(norm(v), t) for t, v in self._vi.items()]
        # bản CÓ DẤU để ưu tiên khớp chính xác ("váy" không bị lẫn với "vảy", "vây")
        self._vi_raw = [(v.strip().lower(), t) for t, v in self._vi.items()]
        self._en_keys = sorted((norm(t), t) for t in self._info)
        self._en_norm = [k for k, _ in self._en_keys]
        self._by_count = sorted(self._info, key=lambda t: -self._info[t][1])
        self.loaded = True
        return self

    # ------------------------------------------------------------------ truy vấn
    def vi_of(self, tag):
        return self._vi.get(tag) or self._vi.get(tag.replace(" ", "_")) or ""

    def label_of(self, tag):
        """Nghĩa tiếng Việt để hiển thị.

        Tag mượn nguyên văn tiếng nước ngoài (bikini, kimono, bikini_top...) có bản
        dịch trùng khít với tag nên KHÔNG nằm trong file translation; khi đó hiển thị
        chính tag kèm ghi chú để người dùng không tưởng là thiếu dữ liệu.
        """
        vi = self.vi_of(tag)
        if vi:
            return vi
        return f"{tag.replace('_', ' ')} (từ mượn, giữ nguyên)"

    def info_of(self, tag):
        return self._info.get(tag) or self._info.get(tag.replace(" ", "_"))

    def group_of(self, tag):
        info = self.info_of(tag)
        cat = info[0] if info else None
        spaced = tag.replace("_", " ")
        return G.classify(spaced if spaced in self._info else tag,
                          cat, self._sys_group.get(tag) or self._sys_group.get(spaced))

    def result(self, tag, score=0):
        info = self.info_of(tag)
        cat, pc = info if info else (5, 0)
        return TagResult(tag, self.vi_of(tag), cat, pc, self.group_of(tag), score)

    def __len__(self):
        return len(self._info)

    def stats(self):
        translated = sum(1 for t in self._info if t in self._vi)
        return {
            "tổng_số_tag": len(self._info),
            "có_nghĩa_tiếng_việt": translated,
            "tag_hệ_thống": len(self._sys_group),
            "bí_danh": len(self._alias),
        }

    # ------------------------------------------------------------------ tìm kiếm
    def search(self, query, cats=None, limit=30, min_count=0):
        """Tra cứu: nhận cả tiếng Việt (có/không dấu) lẫn tag tiếng Anh."""
        q = (query or "").strip()
        cats = set(cats) if cats else None
        if not q:
            return self._top_by_count(limit, cats, min_count)

        nq = norm(q)
        raw = q.lower().replace("_", " ")
        scored = {}

        def add(tag, score):
            info = self._info.get(tag)
            if info is None:
                return
            if cats and info[0] not in cats:
                return
            if min_count and info[1] < min_count:
                return
            scored[tag] = max(scored.get(tag, 0), score)

        # 1a) khớp nghĩa tiếng Việt CÓ DẤU trước (ưu tiên cao nhất):
        #     gõ "váy" phải ra skirt chứ không phải "vảy" (scales) hay "vây" (fins).
        q_low = q.strip().lower()
        if unaccent(q_low) != q_low:
            for rvi, tag in self._vi_raw:
                if rvi == q_low:
                    add(tag, 1500)
                elif rvi.startswith(q_low):
                    add(tag, 1150 - min(len(q_low), 100))
                elif len(q_low) >= 2 and q_low in rvi:
                    add(tag, 800 - min(len(q_low), 100))

        # 1b) khớp nghĩa tiếng Việt đã bỏ dấu (exact > prefix > substring)
        for nvi, tag in self._vi_items:
            if nvi == nq:
                add(tag, 1200)
            elif nvi.startswith(nq):
                add(tag, 900 - min(len(nq), 100))
            elif len(nq) >= 2 and nq in nvi:
                add(tag, 550 - min(len(nq), 100))

        # 1c) khớp "đủ mọi từ" theo bất kỳ thứ tự nào: "nhìn người xem" vẫn phải ra
        #     looking_at_viewer dù bản dịch là "nhìn vào người xem".
        tokens = nq.split()
        if len(tokens) >= 2 and len(scored) < limit * 3:
            for nvi, tag in self._vi_items:
                if all(tok in nvi.split() for tok in tokens):
                    add(tag, 680 - min(len(nq), 100))

        # 2) khớp tag tiếng Anh: exact / prefix (dùng bisect cho nhanh) / alias
        key = norm(q)
        i = bisect.bisect_left(self._en_norm, key)
        n = len(self._en_norm)
        scanned = 0
        while i < n and scanned < 4000:
            cand = self._en_norm[i]
            if not cand.startswith(key):
                break
            tag = self._en_keys[i][1]
            add(tag, 1000 if cand == key else 800 - min(scanned // 20, 200))
            i += 1
            scanned += 1
        if raw in self._alias:
            add(self._alias[raw], 950)
        # 3) substring tiếng Anh trên tập tag phổ biến (chỉ khi còn thiếu kết quả)
        if len(scored) < limit:
            for tag in self._by_count[:80000]:
                if len(scored) >= limit * 6:
                    break
                if raw in tag.replace("_", " "):
                    add(tag, 300)

        if not scored:
            return []
        ranked = sorted(scored.items(), key=lambda kv: (-kv[1], -self._info[kv[0]][1]))
        return [self.result(t, s) for t, s in ranked[:limit]]

    def _top_by_count(self, limit, cats=None, min_count=0):
        out = []
        for tag in self._by_count:
            cat, pc = self._info[tag]
            if cats and cat not in cats:
                continue
            if pc < min_count:
                continue
            out.append(self.result(tag, 0))
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------ duyệt theo nhóm
    def top_in_group(self, group, limit=40, min_count=100, cats=None):
        """Tag phổ biến nhất của một nhóm — dùng cho chế độ duyệt thư viện."""
        cache_key = (min_count, tuple(sorted(cats)) if cats else None)
        table = self._group_cache.get(cache_key)
        if table is None:
            table = defaultdict(list)
            for tag in self._by_count:
                cat, pc = self._info[tag]
                if pc < min_count:
                    break            # _by_count đã sắp giảm dần nên dừng được
                if cats and cat not in cats:
                    continue
                table[self.group_of(tag)].append(tag)
            self._group_cache[cache_key] = table
        tags = table.get(group, [])
        return [self.result(t) for t in tags[:limit]]

    def group_sizes(self, min_count=100, cats=None):
        cache_key = (min_count, tuple(sorted(cats)) if cats else None)
        if cache_key not in self._group_cache:
            self.top_in_group("other", 1, min_count, cats)
        return {g: len(v) for g, v in self._group_cache[cache_key].items()}

    # ------------------------------------------------------------------ tag ngẫu nhiên
    def random_tags(self, n=12, seed=None, min_count=1000, avoid_groups=("meta",),
                    allow_nsfw=False):
        """Bốc ngẫu nhiên tag phổ biến, trải đều các nhóm — dùng cho nút 'Ngẫu nhiên'.

        Mặc định LOẠI tag nhóm 18+ (kho merged gồm cả e621 nên rất nhiều tag loại này);
        chỉ đưa vào khi người dùng bật `allow_nsfw=True`.
        """
        import random
        rnd = random.Random(seed)
        skip = set(avoid_groups)
        if not allow_nsfw:
            skip.add("sexual")
        pool = []
        for t in self._by_count[:40000]:
            cat, pc = self._info[t]
            if pc < min_count or self.group_of(t) in skip:
                continue
            if not allow_nsfw:
                # Kho merged gộp cả e621 (cat 7/12) vốn nhiều nội dung người lớn và
                # giải phẫu thú; chế độ an toàn chỉ lấy tag Danbooru (cat 0/5).
                if cat not in (0, 5) or not self._vi.get(t):
                    continue
            pool.append(t)
        rnd.shuffle(pool)
        picked, seen_groups = [], defaultdict(int)
        for tag in pool:
            g = self.group_of(tag)
            if seen_groups[g] >= 3:          # không quá 3 tag mỗi nhóm
                continue
            seen_groups[g] += 1
            picked.append(tag)
            if len(picked) >= n:
                break
        return [self.result(t) for t in picked]


_INDEX = None


def get_index(root=None):
    """Singleton: cả app Gradio và extension Forge dùng chung một mục lục."""
    global _INDEX
    if _INDEX is None:
        _INDEX = TagIndex(root)
    return _INDEX
