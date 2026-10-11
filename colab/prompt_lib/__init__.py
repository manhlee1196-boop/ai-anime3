"""Bộ dựng prompt tiếng Việt cho WAI-Illustrious v17.

Dùng chính kho tag đã dịch ở thư mục gốc repo (`danbooru_e621.csv` +
`danbooru_e621_vi_translation.csv`) làm nguồn nhắc prompt.

Cách dùng nhanh:
    from prompt_lib import get_index, PromptBuilder
    index = get_index()
    builder = PromptBuilder(index)
    hits = index.search("áo dài")            # tra tiếng Việt -> tag tiếng Anh
    out = builder.assemble("1girl, ao_dai, long_hair", rating_id="general")
    print(out["prompt"], out["negative"])
"""

from .builder import PromptBuilder, parse_pieces, render
from .groups import BROWSE_GROUPS, GROUP_LABELS, GROUP_ORDER, classify, strip_namespace
from .index import (CATEGORY_NAMES, TagIndex, TagResult, find_repo_root, get_index,
                    norm, unaccent)
from .system_tags import (NEGATIVE_PRESETS, QUALITY_PRESETS, RATINGS, SIZE_PRESETS,
                          SYSTEM_TAGS, UPSCALERS, WAI_DEFAULTS, pick_upscaler)

__all__ = [
    "PromptBuilder", "parse_pieces", "render",
    "GROUP_LABELS", "GROUP_ORDER", "BROWSE_GROUPS", "classify", "strip_namespace",
    "TagIndex", "TagResult", "CATEGORY_NAMES", "find_repo_root", "get_index",
    "norm", "unaccent",
    "SYSTEM_TAGS", "QUALITY_PRESETS", "NEGATIVE_PRESETS", "RATINGS",
    "SIZE_PRESETS", "UPSCALERS", "WAI_DEFAULTS", "pick_upscaler",
]

__version__ = "1.0.0"
