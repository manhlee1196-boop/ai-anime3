"""Mục chọn **thẻ phong cách vẽ** cho bộ dựng prompt.

Đọc `style_tags.csv` ở thư mục gốc repo (do `tools/find_style_tags.py` sinh ra):
506 tag phong cách chia 9 nhóm, mỗi dòng có `tag, vi, category, post_count, nhom, nguon_vi`.

Ba cách chọn trong UI:
  1. **Theo nhóm** — chọn "Chất liệu truyền thống", "Kỹ thuật hoàn thiện"… rồi tick tag.
  2. **Theo công thức sẵn** — 12 combo đã cân sẵn chất liệu + kỹ thuật + ánh sáng.
  3. **Tìm chữ** — gõ "màu nước", "nuoc", "cell"… không cần đúng dấu.

Module thuần stdlib để test được trong CI, không cần Gradio:

    from prompt_lib.styles import StyleLibrary
    lib = StyleLibrary()                 # tự tìm style_tags.csv trong repo
    lib.groups()                         # ['Chất liệu truyền thống', ...]
    lib.choices("Kỹ thuật hoàn thiện")   # ['cel_shading  ·  đổ bóng kiểu cel', ...]
    lib.tags_of(choices)                 # ['cel_shading', 'flat_colors', ...]
    lib.preset("Tranh màu nước")         # ['watercolor_(medium)', ...]
"""

import csv
import os
import unicodedata

STYLE_CSV = "style_tags.csv"

# Thứ tự hiển thị mong muốn; nhóm lạ (nếu CSV có thêm) xếp cuối theo bảng chữ cái.
GROUP_ORDER = [
    "Chất liệu truyền thống",
    "Chất liệu số & CG",
    "Kỹ thuật hoàn thiện",
    "Ánh sáng",
    "Trường phái & mỹ thuật",
    "Phong cách thể loại",
    "Thời kỳ & thiết kế",
    "Nguồn & định dạng (dùng kèm)",
    "Phong cách tác giả / series",
]

# Công thức sẵn: nhãn -> (tag ..., ghi chú ngắn). Tag phải có thật trong style_tags.csv
# (test_style_tags.py kiểm tra điều này).
PRESETS = {
    "Tranh màu nước": (
        ["watercolor_(medium)", "traditional_media_(artwork)", "painterly", "soft_lighting"],
        "chất lỏng, loang màu, viền mềm"),
    "Anime cel-shading (TV)": (
        ["anime_coloring", "cel_shading", "flat_colors", "line_art"],
        "nét sạch, màu phẳng, đúng chất anime truyền hình"),
    "Anime thập niên 1990": (
        ["1990s_(style)", "retro_artstyle", "cel_shading", "retro_anime_style"],
        "nét mảnh, màu bết kiểu VHS"),
    "Tranh khắc gỗ Nhật": (
        ["ukiyo-e", "sumi-e", "ink_wash_painting", "nihonga"],
        "mảng phẳng, mực loang, viền đậm"),
    "Art Nouveau / kính màu": (
        ["art_nouveau", "stained_glass", "painterly"],
        "đường cong trang trí, viền chì"),
    "Tranh sơn dầu cổ điển": (
        ["oil_painting_(medium)", "painterly", "impasto", "chiaroscuro"],
        "dày màu, tương phản sáng tối mạnh"),
    "3D / CG": (
        ["3d_(artwork)", "blender_(artwork)", "photorealistic", "rim_lighting"],
        "khối, phản sáng — nhớ bỏ nếu muốn 2D"),
    "Pixel art game cũ": (
        ["pixel_art", "pixel_animation", "limited_palette", "dithering"],
        "điểm ảnh rõ, bảng màu hẹp"),
    "Truyện tranh đen trắng": (
        ["comic", "greyscale", "screentone", "hatching"],
        "khung truyện, tông chấm, nét gạch"),
    "Phác thảo chì": (
        ["sketch", "graphite_(medium)", "hatching", "monochrome"],
        "nét nháp, chưa tô màu"),
    "Anime hiện đại chi tiết": (
        ["anime_style", "soft_shading", "detailed_shading", "high_contrast"],
        "bóng mềm nhiều lớp, độ chi tiết cao"),
    "Hoạt hình cổ (rubber hose)": (
        ["toon_(style)", "rubber_hose_style", "fleischer_style_toon"],
        "nét tròn, không khớp nối, kiểu 1930"),
}

SEP = "  ·  "


def unaccent(text):
    """Bỏ dấu tiếng Việt: 'màu nước' -> 'mau nuoc'."""
    nfkd = unicodedata.normalize("NFD", str(text))
    out = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return out.replace("đ", "d").replace("Đ", "D")


def norm(text):
    """Chuẩn hoá để so khớp: thường, bỏ dấu, '_' thành khoảng trắng."""
    t = unaccent(str(text).strip().lower()).replace("_", " ")
    return " ".join(t.split())


class StyleTag:
    """Một tag phong cách: tag tiếng Anh, nghĩa Việt, số bài đăng, nhóm."""

    __slots__ = ("tag", "vi", "category", "post_count", "group")

    def __init__(self, tag, vi, category, post_count, group):
        self.tag = tag
        self.vi = vi
        self.category = category
        self.post_count = post_count
        self.group = group

    @property
    def strength(self):
        """Độ mạnh thực tế của tag khi đưa vào prompt (theo số bài đăng)."""
        if self.post_count >= 10000:
            return "rất mạnh"
        if self.post_count >= 1000:
            return "rõ"
        if self.post_count >= 300:
            return "yếu"
        return "rất yếu"

    def label(self):
        return f"{self.tag}{SEP}{self.vi}"

    def row(self):
        return [self.tag, self.vi, f"{self.post_count:,}".replace(",", "."),
                self.strength, self.group]

    def __repr__(self):
        return f"<StyleTag {self.tag!r} pc={self.post_count}>"


class StyleLibrary:
    """Kho tag phong cách + nhóm, công thức sẵn và tìm kiếm."""

    def __init__(self, root=None, path=None):
        self.path = path or self._find(root)
        self.items = {}                   # tag -> StyleTag
        self._by_group = {}               # nhóm -> [StyleTag] đã sắp theo post_count
        self._labels = {}                 # nhãn hiển thị -> tag
        if self.path:
            self.load()

    # ------------------------------------------------------------------ nạp
    @staticmethod
    def _find(root=None):
        """Tìm style_tags.csv: ưu tiên root truyền vào, rồi đi ngược từ file này."""
        candidates = []
        if root:
            candidates.append(os.path.join(root, STYLE_CSV))
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(6):
            candidates.append(os.path.join(here, STYLE_CSV))
            parent = os.path.dirname(here)
            if parent == here:
                break
            here = parent
        for cand in candidates:
            if os.path.exists(cand):
                return cand
        return None

    def load(self):
        with open(self.path, encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if len(row) < 6 or row[0] == "tag":
                    continue
                try:
                    item = StyleTag(row[0], row[1], int(row[2]), int(row[3]), row[4])
                except ValueError:
                    continue
                self.items[item.tag] = item
                self._by_group.setdefault(item.group, []).append(item)
                self._labels[item.label()] = item.tag
        for items in self._by_group.values():
            items.sort(key=lambda s: (-s.post_count, s.tag))
        return self

    def __len__(self):
        return len(self.items)

    @property
    def loaded(self):
        return bool(self.items)

    # ------------------------------------------------------------------ truy vấn
    def groups(self):
        known = [g for g in GROUP_ORDER if g in self._by_group]
        extra = sorted(g for g in self._by_group if g not in GROUP_ORDER)
        return known + extra

    def group_sizes(self):
        return {g: len(self._by_group[g]) for g in self.groups()}

    def entries(self, group=None, limit=None):
        items = self._by_group.get(group, []) if group else list(self.items.values())
        items = sorted(items, key=lambda s: (-s.post_count, s.tag))
        return items[:limit] if limit else items

    def choices(self, group=None, query="", limit=None):
        """Nhãn hiển thị cho CheckboxGroup/dropdown (giữ thứ tự phổ biến)."""
        items = self.search(query, group=group) if (query or "").strip() \
            else self.entries(group)
        return [item.label() for item in (items[:limit] if limit else items)]

    def tag_of(self, label):
        """Nhãn -> tag; nhận cả khi người dùng dán thẳng tag tiếng Anh."""
        label = str(label or "").strip()
        if label in self._labels:
            return self._labels[label]
        tag = label.split(SEP)[0].strip()
        return tag if tag in self.items else (label if label in self.items else "")

    def tags_of(self, labels):
        out = []
        for label in labels or []:
            tag = self.tag_of(label)
            if tag and tag not in out:
                out.append(tag)
        return out

    def search(self, query, group=None, limit=80):
        """Tìm trong tag phong cách: theo tag Anh hoặc nghĩa Việt, không cần dấu."""
        q = norm(query)
        pool = self.entries(group)
        if not q:
            return pool[:limit]
        scored = []
        for item in pool:
            ntag, nvi = norm(item.tag), norm(item.vi)
            if ntag == q or nvi == q:
                score = 3
            elif ntag.startswith(q) or nvi.startswith(q):
                score = 2
            elif q in ntag or q in nvi:
                score = 1
            elif all(word in f"{ntag} {nvi}" for word in q.split()):
                score = 1
            else:
                continue
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], -pair[1].post_count))
        return [item for _score, item in scored[:limit]]

    def info(self, tag):
        return self.items.get(tag)

    # ------------------------------------------------------------------ công thức
    def preset_names(self):
        return list(PRESETS)

    def preset(self, name, only_known=True):
        """Danh sách tag của một công thức sẵn (bỏ tag không có trong CSV)."""
        tags = PRESETS.get(name, ([], ""))[0]
        return [t for t in tags if t in self.items] if only_known else list(tags)

    def preset_note(self, name):
        return PRESETS.get(name, ([], ""))[1]

    def rows(self, tags=None):
        """Bảng để hiện trong Dataframe: tag, nghĩa, số ảnh, độ mạnh, nhóm."""
        items = [self.items[t] for t in tags if t in self.items] if tags \
            else self.entries()
        return [item.row() for item in items]

    def summary(self, group=None):
        items = self.entries(group)
        if not items:
            return "Chưa có tag nào trong nhóm này."
        known = sum(1 for i in items if i.vi)
        return (f"**{len(items)}** tag, **{known}** tag có nghĩa tiếng Việt. "
                f"Mạnh nhất: " + ", ".join(f"`{i.tag}` ({i.post_count:,} ảnh)".replace(",", ".")
                                           for i in items[:3]))


def missing_tags(lib):
    """Tag trong PRESETS không có trong style_tags.csv (dùng cho test/CI)."""
    return {t for tags, _note in PRESETS.values() for t in tags if t not in lib.items}
