/* Hồi quy bridge/TAC token đa từ; Node stdlib. Không Forge/GPU, không sửa source TAC. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../extension/vi-prompt-builder/javascript/vi_prompt.js'), 'utf8');
let passed = 0;
function check(name, fn) { fn(); passed++; console.log('✔ ' + name); }

class Input {
    constructor(value, cursor = value.length) { this._value = value; this.selectionStart = cursor; this.selectionEnd = cursor; this.events = []; }
    get value() { return this._value; }
    set value(value) { this._value = value; }
    dispatchEvent(evt) { this.events.push(evt.type); }
}
const fields = {
    txt2img_prompt: new Input('1girl, (áo dài:1.2), long_hair'),
    txt2img_neg_prompt: new Input('custom negative'),
};
const status = {textContent: ''};
const context = vm.createContext({console, module: {exports: {}}, Event: class { constructor(type) { this.type = type; } },
    document: {querySelector(selector) {
        if (selector === '#vi_prompt_fill_note') return status;
        const id = selector.match(/^#(\S+) (textarea|input)$/)?.[1]; return fields[id] || null;
    }},
});
vm.runInContext(`var translations = new Map([['ao_dai', 'áo dài'], ['long_hair', 'tóc dài'], ['skirt', 'váy'], ['scales', 'vảy'], ['hat', 'mũ'], ['singing', 'hát'], ['cloud', 'mây']]);
var allTags = [['hat'], ['may']], extras = [];
var calls = [];
async function autocomplete(area, prompt, fixedTag) { calls.push(fixedTag); }
async function insertTextAtCursor(area, result, word) { calls.push({word, cursor: area.selectionStart}); }
`, context);
vm.runInContext(source, context);
const api = context.module.exports;
check('Chỉ thay Việt → Anh, giữ mục khác và trọng số', () => {
    assert.equal(api.viPromptMerge('1girl, (áo dài:1.2), long_hair', 'ao_dai, masterpiece'),
        '1girl, (ao_dai:1.2), long_hair, masterpiece');
    assert.equal(api.viPromptMerge('1girl, ao_dai', 'ao_dai'), '1girl, ao_dai');
    assert.equal(api.viPromptMerge('1girl, áo dài, ao_dai', 'ao_dai'), '1girl, ao_dai');
    assert.equal(api.viPromptMerge('vảy', 'skirt'), 'vảy, skirt');
    assert.equal(api.viPromptMerge('hat, hát, may', 'singing, cloud'), 'hat, singing, may, cloud');
    assert.equal(api.viPromptMerge('1girl, 1girl, ( áo dài :1.20 ), (ao_dai:1.3)', 'ao_dai'),
        '1girl, 1girl, ( ao_dai :1.20 ), (ao_dai:1.3)');
    assert.equal(api.viPromptMerge('(áo dài:1.2)'.normalize('NFD'), 'ao_dai'), '(ao_dai:1.2)');
});
check('Token giữa prompt/cursor trong trọng số, LoRA và schedule không bị sửa', () => {
    const s = 'solo, (áo dài:1.2), long_hair';
    const token = api.viPromptActiveToken(new Input(s, s.indexOf('dài') + 3));
    assert.equal(token.text, 'áo dài');
    assert.equal(s.slice(token.start, token.end), 'áo dài');
    assert.equal(api.viPromptActiveToken(new Input('<lora:a:0.8>')), null);
    assert.equal(api.viPromptActiveToken(new Input('<_<, <3, áo dài')).text, 'áo dài');
    assert.equal(api.viPromptActiveToken(new Input('[a,b:c]')), null);
    assert.equal(api.viPromptActiveToken(new Input(s, s.indexOf('1.2') + 2)), null);
    assert.equal(api.viPromptActiveToken(new Input('(áo dài:1.2)')).text, 'áo dài');
    assert.equal(api.viPromptActiveToken(new Input('((áo dài):1.2)')).text, 'áo dài');
});
check('Bridge đồng bộ native setter + input; default không xóa nội dung khác', () => {
    api.viPromptFill('ao_dai, masterpiece', 'bad anatomy', false);
    assert.equal(fields.txt2img_prompt.value, '1girl, (ao_dai:1.2), long_hair, masterpiece');
    assert.equal(fields.txt2img_neg_prompt.value, 'custom negative, bad anatomy');
    assert.deepEqual(fields.txt2img_prompt.events, ['input', 'change']);
});
check('Hoàn tác và thay toàn bộ chỉ khi được chọn', () => {
    api.viPromptUndo();
    assert.equal(fields.txt2img_prompt.value, '1girl, (áo dài:1.2), long_hair');
    api.viPromptFill('ao_dai', '', true);
    assert.equal(fields.txt2img_prompt.value, 'ao_dai');
    assert.equal(fields.txt2img_neg_prompt.value, '');
    // Lần thứ hai chỉ đổi positive: Undo phải giữ negative của snapshot mới,
    // không lấy negative cũ từ một thao tác trước đó.
    api.viPromptFill('ao_dai', 'lowres', false);
    api.viPromptFill('ao_dai, long_hair', 'lowres', false);
    api.viPromptUndo();
    assert.equal(fields.txt2img_prompt.value, 'ao_dai');
    assert.equal(fields.txt2img_neg_prompt.value, 'lowres');
    // Đưa fixture về trạng thái phục vụ nhóm kiểm tra kế tiếp.
    api.viPromptFill('ao_dai', '', true);
});
check('Prompt rỗng/thiếu field không báo thành công giả hay xóa', () => {
    api.viPromptFill('', '', true);
    assert.equal(fields.txt2img_prompt.value, 'ao_dai');
    const neg = fields.txt2img_neg_prompt; delete fields.txt2img_neg_prompt;
    api.viPromptFill('solo', 'lowres');
    assert.equal(fields.txt2img_prompt.value, 'ao_dai');
    assert.ok(status.textContent.includes('Không tìm thấy'));
    fields.txt2img_neg_prompt = neg;
});

async function main() {
    assert.equal(api.viPromptInstallTacHooks(), true);
    assert.equal(api.viPromptInstallTacHooks(), true); // idempotent
    const area = new Input('1girl, áo dài');
    await vm.runInContext('autocomplete', context)(area, area.value, null);
    assert.equal(context.calls.at(-1), 'áo dài');
    await vm.runInContext('insertTextAtCursor', context)(area, {text: 'ao_dai', type: 1}, 'dài');
    assert.equal(context.calls.at(-1).word, 'áo dài');
    for (const [typed, expected] of [['áo dài'.normalize('NFD'), 'áo dài'], ['ao dai', 'ao_dai'], ['toc dai', 'tóc dài']]) {
        const input = new Input(typed);
        await vm.runInContext('autocomplete', context)(input, typed, null);
        assert.equal(context.calls.at(-1), expected);
        await vm.runInContext('insertTextAtCursor', context)(input, {text: 'ao_dai', type: 1}, 'dai');
        assert.equal(context.calls.at(-1).word, typed);
    }
    console.log('✔ Adapter tìm/chèn toàn cụm Việt, Unicode NFD và cụm không dấu'); passed++;

    let loadedHook, updateHook;
    const delayed = vm.createContext({module: {exports: {}}, onUiLoaded(fn) { loadedHook = fn; },
        onUiUpdate(fn) { updateHook = fn; }});
    vm.runInContext(source, delayed);
    assert.equal(loadedHook(), false); // TAC chưa được nạp.
    vm.runInContext('async function autocomplete() {}; async function insertTextAtCursor() {};', delayed);
    assert.equal(updateHook(), true);
    const patched = vm.runInContext('autocomplete', delayed);
    assert.equal(updateHook(), true);
    assert.equal(vm.runInContext('autocomplete', delayed), patched);
    console.log('✔ Hook retry khi TAC nạp muộn, không bọc nhiều lần'); passed++;
    const lora = new Input('<lora:áo dài:0.8>');
    await vm.runInContext('insertTextAtCursor', context)(lora, {text: 'other', type: 9}, 'dài');
    assert.equal(context.calls.at(-1).word, 'dài');
    console.log('✔ Không intercept LoRA/wildcard/embedding'); passed++;

    if (process.env.TAC_AUDIT_SOURCE) {
        const tac = fs.readFileSync(process.env.TAC_AUDIT_SOURCE, 'utf8');
        const start = tac.indexOf('async function insertTextAtCursor(');
        const end = tac.indexOf('\nfunction addResultsToList(', start);
        assert.ok(start >= 0 && end > start);
        const actual = vm.createContext({console, module: {exports: {}}, Event: class {}, document: context.document});
        vm.runInContext(`var translations = new Map([['ao_dai', 'áo dài']]);
var TAC_CFG = {replaceUnderscores: false, escapeParentheses: true, appendComma: true, appendSpace: true, frequencySort: false, modelKeywordCompletion: 'Never'};
var ResultType = {tag:1, extra:2, wildcardFile:5, yamlWildcard:6, umiWildcard:7, hypernetwork:8, lora:9, lyco:10, wildcardTag:4};
var QUEUE_SANITIZE = 0, QUEUE_AFTER_INSERT = 1, previousTags = [], hideBlocked = false;
var WEIGHT_REGEX = /\\(([^()]+)\\)/g;
function TAG_REGEX() { return /[^,]+/g; }
function escapeRegExp(s) { return s.replace(/[.*+?^$\x7b\x7d()|[\]\\\\]/g, '\\\\$&'); }
async function processQueueReturn() { return []; }
function updateInput(area) { area.synced = true; }
function isVisible() { return false; }
async function autocomplete() {}
`, actual);
        vm.runInContext(tac.slice(start, end), actual);
        vm.runInContext(source, actual);
        actual.module.exports.viPromptInstallTacHooks();
        const rows = [
            ['1girl, áo dài', '1girl, ao_dai, '],
            ['1girl, (áo dài:1.2), long_hair', '1girl, (ao_dai:1.2), long_hair'],
            ['1girl, (áo dài), long_hair', '1girl, (ao_dai), long_hair'],
            ['1girl, ((áo dài):1.2), long_hair', '1girl, ((ao_dai):1.2), long_hair'],
            ['1girl, ( áo dài :1.20 ), long_hair', '1girl, ( ao_dai :1.20 ), long_hair'],
            ['1girl, (áo dài:1.2)', '1girl, (ao_dai:1.2)'],
            ['1girl, áo dài'.normalize('NFD'), '1girl, ao_dai, '],
            ['1girl, ao dai', '1girl, ao_dai, '],
        ];
        for (const [value, expected] of rows) {
            const sourceBody = value.includes('ao dai') ? 'ao dai'
                : value.includes('áo dài') ? 'áo dài' : 'áo dài'.normalize('NFD');
            const cursor = value.endsWith(')') ? value.length : value.indexOf(sourceBody) + sourceBody.length;
            const input = new Input(value, cursor);
            await vm.runInContext('insertTextAtCursor', actual)(input, {text: 'ao_dai', type: 1}, 'dài');
            assert.equal(input.value, expected);
            assert.equal(input.synced, true);
        }
        console.log('✔ Hàm insertTextAtCursor nguyên bản TAC vượt hồi quy cụm Việt/weight/mục khác'); passed++;
    } else console.log('ℹ Bỏ qua upstream thật: đặt TAC_AUDIT_SOURCE=/path/tagAutocomplete.js để kiểm thêm');
    console.log(`${passed} nhóm JS đạt (DOM stub/CPU, không phải browser/GPU benchmark)`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
