/** Prompt VN: thay đúng mục Việt, giữ mục khác; bridge Gradio + TAC đa từ. */
'use strict';

const viPromptHistory = new WeakMap();
let viPromptTranslationCache = {map: null, size: -1, file: '', exact: new Map()};
let viPromptTagCache = {tags: null, extras: null, size: -1, extraSize: -1, file: '', keys: new Set()};

function viPromptNorm(value) {
    return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[đĐ]/g, 'd').replace(/_/g, ' ').trim().toLowerCase().replace(/\s+/g, ' ');
}

function viPromptParts(text) {
    text = String(text || '');
    const result = [], stack = [], pairs = {'(': ')', '[': ']', '<': '>'};
    let start = 0, escaped = false;
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (escaped) { escaped = false; continue; }
        if (c === '\\') { escaped = true; continue; }
        if (c === '<' && !/^<(?:lora|lyco|embedding|hypernet):/i.test(text.slice(i))) continue;
        if (pairs[c]) stack.push(pairs[c]);
        else if (stack.length && c === stack[stack.length - 1]) stack.pop();
        else if (c === ',' && !stack.length) {
            result.push({start, end: i, text: text.slice(start, i)}); start = i + 1;
        }
    }
    result.push({start, end: text.length, text: text.slice(start)});
    return result;
}

function viPromptBody(piece) {
    let start = piece.search(/\S/), end = piece.trimEnd().length, weighted = false;
    const originalStart = start;
    if (start < 0 || /^(?:<|__|\[|BREAK\b)/.test(piece.slice(start))) return null;
    while (start < end) {
        while (start < end && /\s/.test(piece[start])) start++;
        while (end > start && /\s/.test(piece[end - 1])) end--;
        if (piece[start] === '(' && piece[end - 1] === ')') { start++; end--; continue; }
        const match = weighted ? null : piece.slice(start, end).match(/^(.+?):(\d+(?:\.\d+)?|\.\d+)$/s);
        if (match && (start > originalStart || !/^\d+$/.test(match[1].trim()))) {
            end = start + match[1].length; weighted = true; continue;
        }
        break;
    }
    if (/^(?:<|__|\[|BREAK\b)/.test(piece.slice(start, end))) return null;
    return {start, end, text: piece.slice(start, end)};
}

function viPromptTranslation(tag) {
    // TAC dùng lexical Map toàn cục, không nhất thiết window.translations.
    try { return typeof translations !== 'undefined' ? translations.get(tag) : null; }
    catch (_) { return null; }
}

function viPromptLiteral(value) {
    return String(value || '').normalize('NFC').trim().toLowerCase().replace(/ /g, '_');
}

function viPromptKnownLiteral(value) {
    const literal = viPromptLiteral(value);
    try {
        if (typeof translations !== 'undefined' && translations.has(literal)) return true;
        const tags = typeof allTags !== 'undefined' ? allTags : [];
        const extra = typeof extras !== 'undefined' ? extras : [];
        const file = typeof TAC_CFG !== 'undefined' && TAC_CFG ? TAC_CFG.tagFile || '' : '';
        if (viPromptTagCache.tags !== tags || viPromptTagCache.extras !== extra ||
            viPromptTagCache.size !== tags.length || viPromptTagCache.extraSize !== extra.length || viPromptTagCache.file !== file) {
            const keys = new Set(tags.map(row => viPromptLiteral(row[0])));
            for (const row of extra) keys.add(viPromptLiteral(row[0]));
            viPromptTagCache = {tags, extras: extra, size: tags.length, extraSize: extra.length, file, keys};
        }
        return viPromptTagCache.keys.has(literal);
    } catch (_) { return false; }
}

function viPromptSame(a, b, meaning) {
    if (viPromptLiteral(a) === viPromptLiteral(b)) return true;
    // Không hiểu nhầm hat thành hát hoặc tên riêng may thành mây.
    if (viPromptKnownLiteral(a) || !meaning) return false;
    const accented = /[\u0300-\u036fđĐ]/.test(a.normalize('NFD'));
    return accented ? a.normalize('NFC').trim().toLowerCase() === meaning.normalize('NFC').trim().toLowerCase()
        : viPromptNorm(a) === viPromptNorm(meaning);
}

function viPromptMerge(current, incoming) {
    let parts = viPromptParts(current).map(p => p.text);
    for (const item of viPromptParts(incoming)) {
        const body = viPromptBody(item.text);
        if (!body) {
            if (item.text.trim() && !parts.some(p => p.trim() === item.text.trim())) parts.push(' ' + item.text.trim());
            continue;
        }
        const meaning = viPromptTranslation(body.text.replace(/ /g, '_')) || viPromptTranslation(body.text);
        let matched = false;
        const seenTarget = new Set();
        parts = parts.map(piece => {
            const old = viPromptBody(piece);
            if (!old || !viPromptSame(old.text, body.text, meaning)) return piece;
            matched = true;
            // Chỉ đổi body; trọng số/emphasis của ô đích là ý định người dùng.
            const replaced = piece.slice(0, old.start) + body.text + piece.slice(old.end);
            const key = replaced.replace(/\s+/g, '');
            if (seenTarget.has(key)) return '';
            seenTarget.add(key);
            return replaced;
        });
        if (!matched) parts.push(' ' + item.text.trim());
    }
    return parts.filter(p => p.trim()).join(',').trim();
}

function viPromptField(id) {
    const root = typeof gradioApp === 'function' ? gradioApp() : document;
    return root.querySelector('#' + id + ' textarea') || root.querySelector('#' + id + ' input');
}

function viPromptWrite(el, value) {
    // Native setter tương thích Gradio/Svelte; chỉ input/change, không ép blur/focus.
    const proto = Object.getPrototypeOf(el), setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
}

function viPromptStatus(message) {
    const root = typeof gradioApp === 'function' ? gradioApp() : document;
    const el = root.querySelector('#vi_prompt_fill_note');
    if (el) el.textContent = message;
}

function viPromptFillTarget(prefix, prompt, negative, replaceAll = false) {
    const pos = viPromptField(prefix + '_prompt'), neg = viPromptField(prefix + '_neg_prompt');
    if (!pos || !neg) { viPromptStatus('❌ Không tìm thấy đủ hai ô prompt; chưa thay đổi dữ liệu.'); return []; }
    if (!String(prompt || '').trim()) { viPromptStatus('⚠️ Chưa dựng positive prompt; không xóa prompt hiện tại.'); return []; }
    const edits = [[pos, prompt], [neg, negative]].map(([el, text]) => ({
        el, before: el.value, after: replaceAll ? String(text || '') : viPromptMerge(el.value, text)
    }));
    if (edits.some(e => e.before !== e.after)) {
        // Một snapshot cho cả hai ô; ô không đổi không giữ lịch sử từ lần cũ.
        for (const e of edits) {
            viPromptHistory.set(e.el, e.before);
            if (e.before !== e.after) viPromptWrite(e.el, e.after);
        }
    }
    viPromptStatus(replaceAll ? '✅ Đã thay toàn bộ prompt theo lựa chọn của bạn. Có thể Hoàn tác.'
        : '✅ Đã ghép/thay mục Việt → Anh; giữ tag khác và trọng số. Chuyển sang ' + prefix + ' để Generate.');
    return [];
}

function viPromptFill(prompt, negative, replaceAll = false) {
    return viPromptFillTarget('txt2img', prompt, negative, replaceAll);
}
function viPromptFillImg2Img(prompt, negative, replaceAll = false) {
    return viPromptFillTarget('img2img', prompt, negative, replaceAll);
}
function viPromptUndo() {
    for (const id of ['txt2img_prompt', 'txt2img_neg_prompt']) {
        const el = viPromptField(id);
        if (el && viPromptHistory.has(el)) { const value = viPromptHistory.get(el); viPromptHistory.delete(el); viPromptWrite(el, value); }
    }
    viPromptStatus('↩️ Đã hoàn tác lần điền gần nhất (trong phiên trình duyệt này).');
    return [];
}

function viPromptActiveToken(area) {
    const cursor = area.selectionStart;
    const part = viPromptParts(area.value).find(p => cursor >= p.start && cursor <= p.end);
    if (!part) return null;
    const body = viPromptBody(part.text);
    if (!body || cursor < part.start + body.start) return null;
    if (cursor > part.start + body.end) {
        // Cho phép chọn sau dấu ')' cuối, nhưng không chèn khi đang sửa số weight.
        const completeEnd = part.start + part.text.trimEnd().length;
        if (!/\)\s*$/.test(part.text.slice(body.end)) || cursor < completeEnd) return null;
    }
    return {...body, start: part.start + body.start, end: part.start + body.end};
}

function viPromptTranslationLookup() {
    if (typeof translations === 'undefined') return new Map();
    const file = typeof TAC_CFG !== 'undefined' && TAC_CFG ? TAC_CFG.translation?.translationFile || '' : '';
    if (viPromptTranslationCache.map !== translations || viPromptTranslationCache.size !== translations.size || viPromptTranslationCache.file !== file) {
        const exact = new Map();
        for (const meaning of translations.values()) {
            const key = viPromptNorm(meaning), values = exact.get(key) || new Set();
            values.add(meaning.normalize('NFC')); exact.set(key, values);
        }
        viPromptTranslationCache = {map: translations, size: translations.size, file, exact};
    }
    return viPromptTranslationCache.exact;
}

function viPromptVietnameseToken(token) {
    if (!token || /[()[\]<>:|]/.test(token.text)) return false;
    if (/[\u0300-\u036fđĐ]/.test(token.text.normalize('NFD'))) return true;
    // Không dấu: chỉ lấy cụm nhiều từ khớp bản dịch, không đoán câu tiếng Anh.
    if (!/\s/.test(token.text)) return false;
    try { return viPromptTranslationLookup().has(viPromptNorm(token.text)); }
    catch (_) { return false; }
}

function viPromptSearchToken(token) {
    const text = token.text.normalize('NFC');
    if (/[\u0300-\u036fđĐ]/.test(text.normalize('NFD'))) return text;
    if (viPromptKnownLiteral(text)) return viPromptLiteral(text);
    // Search upstream không bỏ dấu: chỉ khôi phục dấu khi nghĩa duy nhất.
    // Các cụm không dấu đa nghĩa không tự chọn một bản dịch ngẫu nhiên.
    try {
        const meanings = viPromptTranslationLookup().get(viPromptNorm(text));
        if (meanings?.size === 1) return meanings.values().next().value;
    } catch (_) { /* TAC chưa có translation map */ }
    return text;
}

function viPromptInstallTacHooks() {
    // Adapter, không sửa file của tagcomplete. Chỉ thay token đa từ tại con trỏ,
    // chỉ result tag/extra; LoRA/embedding/wildcard/style giữ xử lý upstream.
    if (typeof autocomplete !== 'function' || typeof insertTextAtCursor !== 'function') return false;
    if (autocomplete.viPromptPatched) return true;
    const originalAuto = autocomplete, originalInsert = insertTextAtCursor;
    const wrappedAuto = function(area, prompt, fixedTag = null) {
        const token = viPromptActiveToken(area);
        return originalAuto.call(this, area, prompt,
            fixedTag === null && viPromptVietnameseToken(token) ? viPromptSearchToken(token) : fixedTag);
    };
    wrappedAuto.viPromptPatched = true;
    autocomplete = wrappedAuto;
    insertTextAtCursor = async function(area, result, word, ...rest) {
        const token = viPromptActiveToken(area);
        if (!((result.type === 1 || result.type === 2) && viPromptVietnameseToken(token)))
            return originalInsert.call(this, area, result, word, ...rest);
        const prefix = area.value.slice(0, token.start), suffix = area.value.slice(token.end);
        // TAC mặc định chỉ dùng từ cuối ('dài'), để lại 'áo'. Dùng cả 'áo dài'.
        // Đưa cursor về cuối body để regex chỉ thay đúng phạm vi, giữ :1.2).
        area.selectionStart = token.end; area.selectionEnd = token.end; word = token.text;
        const returned = await originalInsert.call(this, area, result, word, ...rest);
        // Upstream có thể thêm ', ' ngay trước ')' hoặc ' :weight'. Chỉ bỏ phần
        // separator vừa thêm trong vỏ emphasis; không đổi config/sanitizer/queue TAC.
        if (/^\s*[:)]/.test(suffix) && !/^[,:]/.test(suffix) &&
            area.value.startsWith(prefix) && area.value.endsWith(suffix)) {
            const cfg = typeof TAC_CFG !== 'undefined' && TAC_CFG ? TAC_CFG : {};
            const separator = (cfg.appendComma ? ',' : '') + (cfg.appendSpace ? ' ' : '');
            const inserted = area.value.slice(prefix.length, area.value.length - suffix.length);
            if (separator && inserted.endsWith(separator)) {
                const clean = inserted.slice(0, -separator.length);
                viPromptWrite(area, prefix + clean + suffix);
                area.selectionStart = prefix.length + clean.length;
                area.selectionEnd = area.selectionStart;
            }
        }
        return returned;
    };
    return true;
}
if (typeof onUiLoaded === 'function') onUiLoaded(viPromptInstallTacHooks);
// TAC khởi tạo từ onUiUpdate; retry không dùng timer, patch idempotent.
if (typeof onUiUpdate === 'function') onUiUpdate(viPromptInstallTacHooks);

// Chỉ dành cho hồi quy Node; khi Forge chạy không có module.exports.
if (typeof module !== 'undefined' && module.exports) module.exports = {
    viPromptNorm, viPromptParts, viPromptBody, viPromptMerge, viPromptActiveToken,
    viPromptInstallTacHooks, viPromptFill, viPromptUndo
};
