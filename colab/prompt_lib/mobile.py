"""Bản tối ưu trình duyệt điện thoại — MỘT nguồn CSS/JS cho cả ba bề mặt.

Ba nơi người dùng mở bằng điện thoại dùng chung đúng bộ quy tắc ở đây:

  1. App Gradio độc lập ``colab/prompt_builder.py`` — nhận qua ``css=``/``head=``
     (Gradio <6: ``Blocks(...)``; Gradio >=6: ``launch(...)``, giống ``theme``).
  2. Tab "Prompt VN" trong Forge — Forge/A1111 tự nạp ``style.css`` ở thư mục
     gốc extension và mọi file trong ``javascript/``; hai file đó được SINH từ
     module này bằng ``colab/make_mobile_assets.py`` (không sửa tay).
  3. Các tab gốc của Forge (txt2img/img2img) — ``style.css`` là toàn cục nên
     chúng cũng được hưởng các mục chung (nút Generate, ô prompt, gợi ý tag).

Nguyên tắc an toàn: ngoài vài quy tắc nền vô hại ở Mục 1, mọi quy tắc đều nằm
trong ``@media (max-width: ...)`` hoặc ``@media (pointer: coarse)`` — màn hình
máy tính không đổi chút nào. CSS chỉ nhắm vào class ``wai-*`` do chính UI của
repo gắn (``elem_classes``) và selector phần tử bền vững qua các bản Gradio,
không dựa vào class băm kiểu ``svelte-xxxx``.

Module này KHÔNG import gradio để test/CI chạy được không cần UI.
Chi tiết từng mục cho người dùng: ``colab/MOBILE.md``.
"""

# Điểm gãy dùng khắp nơi: <=900px xếp một cột (hai cột scale=5 cạnh nhau bị ép
# còn <450px mỗi cột, không gõ nổi), <=640px các hàng đôi cũng xếp dọc,
# <=480px là điện thoại nhỏ (gallery kết quả về 1 cột để xem ảnh dọc).
BP_STACK = 900
BP_PAIR = 640
BP_SMALL = 480

# ----------------------------------------------------------------------
# CSS theo từng mục tối ưu. (id, tiêu đề, css) — giữ đúng thứ tự này vì
# quy tắc ở mục sau được phép thắng mục trước khi cùng độ ưu tiên.
SECTIONS = (
    (
        "viewport-nen",
        "Mục 1 — Viewport, vùng an toàn (tai thỏ) và chống tràn ngang",
        """\
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
.gradio-container { overflow-x: clip; }
.gradio-container * { -webkit-tap-highlight-color: transparent; }
@media (max-width: 900px) {
  .gradio-container {
    max-width: 100% !important;
    padding-left: max(8px, env(safe-area-inset-left)) !important;
    padding-right: max(8px, env(safe-area-inset-right)) !important;
    padding-bottom: calc(12px + env(safe-area-inset-bottom)) !important;
  }
  /* Con của flex mà không co được (min-width mặc định = auto) là nguyên nhân
     số 1 làm UI Gradio tràn ngang trên điện thoại. */
  .gradio-container .wai-row-main > *, .gradio-container .wai-row-2 > * { min-width: 0 !important; }
  .gradio-container img, .gradio-container video, .gradio-container canvas { max-width: 100%; }
}
""",
    ),
    (
        "bo-cuc-mot-cot",
        "Mục 2 — Bố cục một cột: cột trái (tìm tag) xếp trên cột phải (dựng prompt)",
        """\
@media (max-width: 900px) {
  .gradio-container .wai-row-main { flex-wrap: wrap !important; }
  .gradio-container .wai-row-main > .wai-col-main {
    flex: 1 1 100% !important; width: 100% !important; min-width: 0 !important;
  }
}
@media (max-width: 640px) {
  /* Hàng đôi (hai slider, hai dropdown...) cũng xếp dọc để kéo slider bằng
     ngón tay còn đủ chính xác. */
  .gradio-container .wai-row-2 { flex-wrap: wrap !important; }
  .gradio-container .wai-row-2 > * { flex: 1 1 100% !important; }
}
""",
    ),
    (
        "cam-ung",
        "Mục 3 — Cảm ứng: vùng bấm >=48px, núm slider to, bỏ trễ chạm/zoom hai lần",
        """\
@media (pointer: coarse) {
  .gradio-container button, .gradio-container input, .gradio-container select,
  .gradio-container textarea, .gradio-container a { touch-action: manipulation; }
  .gradio-container button:not(.thumbnail-item) { min-height: 48px; padding-top: 10px; padding-bottom: 10px; }
  .gradio-container .gallery button, .gradio-container button.thumbnail-item { min-height: 0; padding: 0; }
  .gradio-container .tab-nav button, .gradio-container [role="tab"] { min-height: 48px; padding: 10px 14px; }
  .gradio-container select { min-height: 48px; }
  .gradio-container input[type="range"] { height: 36px; }
  .gradio-container input[type="range"]::-webkit-slider-thumb { width: 28px; height: 28px; }
  .gradio-container input[type="range"]::-moz-range-thumb { width: 28px; height: 28px; }
  .gradio-container input[type="checkbox"], .gradio-container input[type="radio"] { width: 22px; height: 22px; flex: none; }
  /* Mục chọn trong dropdown Gradio */
  .gradio-container ul.options li, .gradio-container .options li { padding: 12px 10px; min-height: 44px; }
  /* Tiêu đề accordion (vd "Ảnh đã tạo") cũng là vùng bấm */
  .gradio-container .accordion > button, .gradio-container .accordion .label-wrap { min-height: 48px; }
}
""",
    ),
    (
        "nhap-lieu-ban-phim",
        "Mục 4 — Nhập liệu: chữ 16px chống iOS tự phóng to, ô prompt không chiếm hết màn hình",
        """\
@media (max-width: 900px) {
  /* iOS Safari tự zoom khi ô nhập có chữ <16px rồi không thu lại; 16px là
     ngưỡng tắt hành vi đó mà không cần chặn quyền zoom của người dùng. */
  .gradio-container input:not([type="range"]):not([type="checkbox"]):not([type="radio"]),
  .gradio-container textarea, .gradio-container select { font-size: 16px !important; line-height: 1.45; }
  .gradio-container textarea { max-height: 45dvh; }
  .gradio-container .wai-prompt-box textarea { overflow-y: auto; }
}
""",
    ),
    (
        "bang-va-goi-y",
        "Mục 5 — Bảng kết quả & danh sách gợi ý tag: cuộn ngang có kiểm soát, dòng đủ cao để bấm",
        """\
@media (max-width: 900px) {
  .gradio-container .wai-results .table-wrap, .gradio-container .wai-history-table .table-wrap,
  .gradio-container .wai-group-table .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  /* Bảng giữ bề rộng đọc được rồi cuộn ngang, thay vì bị ép cho chữ vỡ vụn. */
  .gradio-container .wai-results table { min-width: 540px; }
  .gradio-container .wai-history-table table { min-width: 520px; }
  .gradio-container .wai-results td, .gradio-container .wai-results th,
  .gradio-container .wai-history-table td, .gradio-container .wai-history-table th { padding: 12px 10px; font-size: 14px; }
  /* Cột tag dính trái để cuộn xem nghĩa Việt mà không lạc mất tag. */
  .gradio-container .wai-results td:first-child, .gradio-container .wai-results th:first-child {
    position: sticky; left: 0; background: var(--block-background-fill, #fff); font-weight: 600;
  }
  /* Bảng trong Markdown (tab hướng dẫn, ghi chú) cũng cuộn ngang thay vì tràn. */
  .gradio-container .prose table, .gradio-container .markdown table, .gradio-container .md table {
    display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%;
  }
  /* Hộp gợi ý của tagcomplete trong txt2img/img2img của Forge (best-effort:
     tên class do extension đó quyết định, không khớp thì vô hại). */
  .autocompleteResults, [class*="autocomplete"] ul { max-height: 45dvh; overflow-y: auto; -webkit-overflow-scrolling: touch; }
}
@media (pointer: coarse) {
  .autocompleteResults li, [class*="autocomplete"] li { padding: 12px 10px; min-height: 44px; }
}
@media (max-width: 480px) {
  .gradio-container .wai-results table, .gradio-container .wai-history-table table { min-width: 460px; }
}
""",
    ),
    (
        "anh-gallery",
        "Mục 6 — Ảnh & gallery: ảnh dọc xem toàn bề rộng, thumbnail lịch sử 3/2 cột",
        """\
@media (max-width: 900px) {
  .gradio-container .wai-gallery { height: auto !important; max-height: 80dvh; }
  .gradio-container .wai-result-gallery .grid,
  .gradio-container .wai-result-gallery [class*="grid"] { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
  .gradio-container .wai-history-gallery .grid,
  .gradio-container .wai-history-gallery [class*="grid"] { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }
  .gradio-container .wai-history-original img { max-height: 70dvh; object-fit: contain; }
}
@media (max-width: 480px) {
  /* Ảnh kết quả thường là ảnh dọc 832x1216: 1 cột mới nhìn rõ mặt/tay. */
  .gradio-container .wai-result-gallery .grid,
  .gradio-container .wai-result-gallery [class*="grid"] { grid-template-columns: repeat(1, minmax(0, 1fr)) !important; }
  .gradio-container .wai-history-gallery .grid,
  .gradio-container .wai-history-gallery [class*="grid"] { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
}
""",
    ),
    (
        "nut-chinh-dinh",
        "Mục 7 — Nút hành động chính dính đáy (kèm vùng an toàn), Generate của Forge dễ bấm",
        """\
@media (max-width: 900px) {
  .gradio-container button.wai-build-action, .gradio-container button.wai-generate-action { width: 100%; min-height: 52px; font-size: 16px; }
  /* Dính trong lúc cuộn xem kết quả bên dưới; sticky (không fixed) nên không
     che nội dung khi bàn phím ảo mở và tự nhả ở cuối cột. */
  .gradio-container button.wai-generate-action {
    position: sticky; bottom: calc(10px + env(safe-area-inset-bottom)); z-index: 30;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.28);
  }
  /* Tab gốc của Forge: id do Forge đặt, chỉ khớp trong trang Forge. */
  #txt2img_generate, #img2img_generate { min-height: 52px; }
  #txt2img_prompt textarea, #txt2img_neg_prompt textarea,
  #img2img_prompt textarea, #img2img_neg_prompt textarea { font-size: 16px !important; }
}
""",
    ),
    (
        "chu-mat-do",
        "Mục 8 — Chữ & mật độ: tiêu đề gọn lại, prompt/tag dài tự xuống dòng để chép",
        """\
@media (max-width: 900px) {
  .gradio-container h1 { font-size: 22px; line-height: 1.3; }
  .gradio-container h2 { font-size: 19px; line-height: 1.35; }
  .gradio-container h3 { font-size: 16px; line-height: 1.4; }
  .gradio-container .prose, .gradio-container .markdown, .gradio-container .md { font-size: 15px; }
  .gradio-container code { overflow-wrap: anywhere; word-break: break-word; }
}
""",
    ),
    (
        "hieu-nang",
        "Mục 9 — Hiệu năng điện thoại yếu: tắt mờ nền đắt tiền, tôn trọng giảm chuyển động",
        """\
@media (max-width: 900px) {
  .gradio-container * { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }
}
@media (prefers-reduced-motion: reduce) {
  .gradio-container *, .gradio-container *::before, .gradio-container *::after {
    animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important;
  }
}
""",
    ),
    (
        "kha-dung-ngang",
        "Mục 10 — Khả dụng: vòng focus rõ khi dùng bàn phím/phím chuyển, chế độ nằm ngang",
        """\
.gradio-container :focus-visible { outline: 3px solid var(--color-accent, #2563eb); outline-offset: 2px; }
@media (max-width: 900px) and (orientation: landscape) {
  .gradio-container .wai-gallery { max-height: 85dvh; }
  .gradio-container textarea { max-height: 35dvh; }
}
""",
    ),
)

_CSS_HEADER = """\
/* ==========================================================================
   Prompt VN — tối ưu trình duyệt điện thoại (10 mục, xem colab/MOBILE.md)
   FILE TỰ SINH từ colab/prompt_lib/mobile.py bởi colab/make_mobile_assets.py
   — KHÔNG sửa tay file đích. Mọi quy tắc (trừ nền Mục 1) nằm trong @media
   bề rộng/cảm ứng nên màn hình máy tính không thay đổi.
   ========================================================================== */
"""


def mobile_css() -> str:
    """Toàn bộ CSS mobile, có banner chia mục để đọc/gỡ lỗi trong DevTools."""
    parts = [_CSS_HEADER]
    for _sid, title, body in SECTIONS:
        parts.append(f"\n/* ----- {title} ----- */\n{body}")
    return "".join(parts)


def render_style_css() -> str:
    """Nội dung ``extension/vi-prompt-builder/style.css`` (Forge tự nạp)."""
    return mobile_css()


# ----------------------------------------------------------------------
# JS tăng cường dần (progressive enhancement): không có JS này UI vẫn dùng
# được nhờ CSS; JS chỉ gắn thuộc tính bàn phím ảo + lazy ảnh + class trạng
# thái. Gõ tag trên điện thoại bị bàn phím tự sửa/viết hoa làm hỏng tag
# (vd "ao_dai" -> "Ao dai") nên các ô prompt/tag tắt autocorrect/autocapitalize.
_JS_CORE = r"""
function waiMobileApply(root) {
    root = root || document;
    var html = document.documentElement;
    var coarse = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
    html.classList.toggle('wai-touch', coarse);
    html.classList.toggle('wai-narrow', window.innerWidth <= 900);
    var meta = document.querySelector('meta[name="viewport"]');
    if (meta && meta.content.indexOf('viewport-fit') === -1) {
        meta.content += ', viewport-fit=cover';
    }
    root.querySelectorAll('.wai-search input, .wai-search textarea').forEach(function (el) {
        el.setAttribute('enterkeyhint', 'search');
        el.setAttribute('autocapitalize', 'none');
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('spellcheck', 'false');
    });
    var promptSel = '.wai-prompt-box textarea, #txt2img_prompt textarea, #txt2img_neg_prompt textarea,' +
        ' #img2img_prompt textarea, #img2img_neg_prompt textarea';
    root.querySelectorAll(promptSel).forEach(function (el) {
        el.setAttribute('enterkeyhint', 'done');
        el.setAttribute('autocapitalize', 'none');
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('spellcheck', 'false');
    });
    root.querySelectorAll('.wai-gallery img, .wai-history-gallery img').forEach(function (img) {
        if (!img.hasAttribute('loading')) img.setAttribute('loading', 'lazy');
        if (!img.hasAttribute('decoding')) img.setAttribute('decoding', 'async');
    });
}
""".strip()

_JS_BOOT = r"""
(function () {
    var timer = null;
    function schedule() {
        if (timer) return;
        timer = setTimeout(function () { timer = null; waiMobileApply(document); }, 250);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule);
    else schedule();
    window.addEventListener('resize', schedule);
    window.addEventListener('orientationchange', schedule);
    if (typeof MutationObserver !== 'undefined' && document.body) {
        new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true});
    }
    if (typeof onUiLoaded === 'function') onUiLoaded(schedule);
    if (typeof onUiUpdate === 'function') onUiUpdate(schedule);
})();
""".strip()


def mobile_js() -> str:
    """JS đầy đủ (hàm lõi + khởi động) — dùng cho cả app độc lập và extension."""
    return _JS_CORE + "\n" + _JS_BOOT + "\n"


def mobile_head() -> str:
    """``head`` cho app Gradio độc lập: meta viewport đầy đủ + JS mobile.

    Gradio tự chèn meta viewport tối thiểu; bản này bổ sung viewport-fit=cover
    để env(safe-area-inset-*) ở Mục 1/7 có tác dụng trên máy tai thỏ. Không đặt
    maximum-scale/user-scalable=no — không tước quyền phóng to của người dùng.
    """
    return (
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "<script>\n" + mobile_js() + "</script>\n"
    )


def render_extension_js() -> str:
    """Nội dung ``extension/vi-prompt-builder/javascript/vi_mobile.js``."""
    return (
        "/** Prompt VN mobile: thuộc tính bàn phím ảo + lazy ảnh + class trạng thái.\n"
        " * TỰ SINH từ colab/prompt_lib/mobile.py bởi colab/make_mobile_assets.py\n"
        " * — KHÔNG sửa tay file này. Xem colab/MOBILE.md. */\n"
        "'use strict';\n" + mobile_js()
        + "\n// Chỉ dành cho hồi quy Node; khi Forge chạy không có module.exports.\n"
        "if (typeof module !== 'undefined' && module.exports) module.exports = {waiMobileApply};\n"
    )


__all__ = [
    "BP_STACK", "BP_PAIR", "BP_SMALL", "SECTIONS",
    "mobile_css", "mobile_head", "mobile_js", "render_style_css", "render_extension_js",
]
