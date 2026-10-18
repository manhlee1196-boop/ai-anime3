/** Prompt VN mobile: thuộc tính bàn phím ảo + lazy ảnh + class trạng thái.
 * TỰ SINH từ colab/prompt_lib/mobile.py bởi colab/make_mobile_assets.py
 * — KHÔNG sửa tay file này. Xem colab/MOBILE.md. */
'use strict';
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

// Chỉ dành cho hồi quy Node; khi Forge chạy không có module.exports.
if (typeof module !== 'undefined' && module.exports) module.exports = {waiMobileApply};
