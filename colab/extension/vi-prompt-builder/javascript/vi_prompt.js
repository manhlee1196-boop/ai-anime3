/**
 * Prompt VN — phần chạy trong trình duyệt của extension.
 *
 * Forge/A1111 tự nạp mọi file .js trong extensions/<tên>/javascript/, nên chỉ cần
 * định nghĩa hàm toàn cục rồi gọi nó từ nút bấm bằng tham số `js=` của Gradio.
 *
 * Nhiệm vụ: điền prompt/negative do bộ dựng tiếng Việt tạo ra vào ô txt2img,
 * mà KHÔNG cần khởi động lại hay gọi API.
 */

function viPromptSetField(id, value) {
    const root = typeof gradioApp === 'function' ? gradioApp() : document;
    let el = root.querySelector('#' + id + ' textarea');
    if (!el) el = root.querySelector('#' + id + ' input');
    if (!el) {
        // dự phòng: ô đầu tiên có id kết thúc bằng tên này (Forge đôi khi thêm hậu tố)
        const candidates = root.querySelectorAll('[id$="' + id + '"] textarea');
        if (candidates.length) el = candidates[0];
    }
    if (!el) {
        console.warn('[Prompt VN] không tìm thấy trường #' + id);
        return false;
    }
    el.value = value === null || value === undefined ? '' : value;
    // Gradio chỉ đồng bộ giá trị về server khi có sự kiện input
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
    el.focus({ preventScroll: true });
    return true;
}

/**
 * @param {string} prompt   positive prompt đã xếp thứ tự
 * @param {string} negative negative prompt
 */
function viPromptFill(prompt, negative) {
    const okPos = viPromptSetField('txt2img_prompt', prompt);
    const okNeg = viPromptSetField('txt2img_neg_prompt', negative);
    if (okPos) {
        console.log('[Prompt VN] đã điền prompt vào txt2img');
    }
    return [];
}

/** Điền vào ô img2img (dùng khi muốn vẽ lại từ ảnh có sẵn). */
function viPromptFillImg2Img(prompt, negative) {
    viPromptSetField('img2img_prompt', prompt);
    viPromptSetField('img2img_neg_prompt', negative);
    return [];
}
