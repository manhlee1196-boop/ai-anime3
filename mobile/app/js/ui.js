/**
 * Giao diện app điện thoại: 4 tab (Tạo ảnh · Kho tag · Thư viện · Máy chủ) + các sheet.
 *
 * Toàn bộ phần "nghĩ" nằm ở core.js / data.js / api.js; file này chỉ nối DOM.
 * Nhờ vậy logic dựng prompt và payload vẫn test được bằng Node mà không cần
 * trình duyệt (xem mobile/tests).
 */

import * as core from './core.js';
import { loadTagData, TagData } from './data.js';
import { ForgeClient, ForgeError } from './api.js';
import * as store from './store.js';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const state = {
  data: null,
  settings: store.loadSettings(),
  selected: [],            // tag đang chọn ở tab Kho tag
  tagLimit: 60,
  tagQuery: '',
  tagGroup: null,
  quickTagOffset: 0,
  suggestions: [],
  suggestionIndex: -1,
  promptComposing: false,
  tagComposing: false,
  styleComposing: false,
  styleQuery: '',
  styleGroup: null,
  busy: false,
  controller: null,
  activeClient: null,
  activeJobId: '',
  source: null,             // Blob ảnh init img2img; chỉ giữ trong phiên, không lưu base64
  sourceUrl: '',
  sourceName: '',
  sourceId: '',
  results: [],             // [{blob, url, name}] — không giữ base64
  lastInfo: null,
  lastSeed: null,
  viewId: null,
  viewUrl: '',
  installEvent: null,
  connected: false,
  connectedModel: '',
  diagnoseBusy: false,
};

// Dùng khi chưa nạp được data/tags.json (app vẫn mở được tab Máy chủ).
// Dùng khi tags.json chưa kịp có mục `colab` (bản APK cũ / dữ liệu lỗi): trỏ tới
// tag phát hành gần nhất, KHÔNG trỏ `main` vì main của repo không chứa notebook.
const FALLBACK_COLAB = {
  repo: 'manhlee1196-boop/ai-anime3',
  branch: 'v1.1.0',
  url: 'https://colab.research.google.com/github/manhlee1196-boop/ai-anime3/blob/v1.1.0/colab/WAI_v17_1click.ipynb',
  cmd_status: 'bash /content/install.sh --status',
  cmd_restart: 'bash /content/install.sh --only launch,verify --restart',
};

// ------------------------------------------------------------------ tiện ích DOM
function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'html') node.innerHTML = value;
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key in node && typeof value !== 'string') node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

let toastTimer = null;
function toast(message, { error = false, ms = 2600 } = {}) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.toggle('error', Boolean(error));
  node.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.add('hidden'), ms);
}

function setStatus(text, { error = false } = {}) {
  const node = $('#status');
  node.textContent = text || '';
  node.classList.toggle('error', Boolean(error));
}

function setProgress(percent) {
  const box = $('#progress');
  const bar = $('#progressBar');
  if (percent === null) {
    box.classList.add('hidden');
    return;
  }
  box.classList.remove('hidden');
  bar.style.width = `${Math.max(4, Math.min(100, percent))}%`;
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(0, Math.round(bytes / 1024))} KB`;
}

function client() {
  return new ForgeClient({
    base: state.settings.apiUrl,
    user: state.settings.user,
    pass: state.settings.pass,
  });
}

function groupOf(tag) {
  return state.data ? state.data.groupIndexOf(tag) : core.OTHER_GROUP;
}

function presets() {
  return state.data?.presets || {};
}

function ratingById(id) {
  const list = presets().ratings || [];
  return list.find((item) => item.id === id) || list[0] || { id: 'general', label: 'An toàn', positive: [], negative: [] };
}

function sizePresets() {
  return presets().sizes || [['Chân dung 1024×1344 (khuyến nghị)', [1024, 1344]]];
}

function currentSize() {
  const list = sizePresets();
  return list[state.settings.sizeIndex] || list[0];
}

// ------------------------------------------------------------------ khởi động
async function init() {
  bindEvents();
  try {
    splash('Đang nạp kho tag…');
    state.data = await loadTagData();
  } catch (error) {
    splash(`⚠️ ${error.message}`, true);
    // vẫn cho dùng Cài đặt/Thư viện dù thiếu kho tag
  }
  if (state.data) {
    fillSelects();
    renderRatingChips();
    renderStylePresets();
    renderStyleGroups();
    renderStyleList();
    renderQuickTags();
    renderTagLibraryMeta();
    splash('Sẵn sàng');
  }
  renderSizeChips();
  const guardAdded = migrateWatermarkGuard();
  applySettingsToForm();
  updatePromptMeta();
  hideSplash();
  if (guardAdded) toast('Đã thêm tag chặn watermark / logo Patreon vào negative');
  pingServer();
  firstRunHint();
  renderServerTab();
  setupResumeWatch();
  renderGallery();
  registerServiceWorker();
}

/**
 * Lần đầu chạy trong APK (https://localhost) chưa có địa chỉ Forge: mở thẳng tab
 * "Máy chủ" — nơi có nút Mở Colab và tự nhận link, thay vì để người dùng đoán.
 */
function firstRunHint() {
  const inApp = location.protocol === 'https:' && location.hostname === 'localhost';
  if (!inApp || state.settings.apiUrl) return;
  setConn('chưa có địa chỉ Forge', 'bad');
  showTab('server');
}

function splash(text, error = false) {
  const node = $('#splashText');
  if (node) node.textContent = text;
  if (error) {
    const bar = document.querySelector('.splash-bar');
    if (bar) bar.classList.add('hidden');
  }
}

function hideSplash() {
  const node = $('#splash');
  if (!node) return;
  node.classList.add('done');
  setTimeout(() => node.remove(), 400);
}

function registerServiceWorker() {
  if (!('serviceWorker' in navigator) || location.protocol !== 'https:') return;
  navigator.serviceWorker.register('sw.js', { scope: './' }).catch((error) => {
    console.warn('Không đăng ký được service worker', error);
  });
}

// ------------------------------------------------------------------ nối sự kiện
function bindEvents() {
  // tab bar
  for (const button of $$('.tab-btn')) {
    button.addEventListener('click', () => showTab(button.dataset.tab));
  }

  // sheet mở/đóng
  $('#settingsBtn').addEventListener('click', () => openSheet('#sheetSettings'));
  $('#styleBtn').addEventListener('click', () => openSheet('#sheetStyle'));
  $('#tagBtn').addEventListener('click', () => { showTab('tags'); $('#tagSearch').focus(); });
  // bấm trạng thái ở thanh trên = mở tab Máy chủ (Colab / đổi link)
  $('#connBtn').addEventListener('click', () => showTab('server'));

  // --- tab Máy chủ
  $('#openColabBtn').addEventListener('click', openColab);
  $('#pasteLinkBtn').addEventListener('click', pasteAndConnect);
  $('#connectBtn').addEventListener('click', () => connectTo($('#serverUrl').value));
  $('#serverUrl').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      connectTo($('#serverUrl').value);
    }
  });
  $('#autoConnect').addEventListener('change', () => {
    state.settings.autoConnect = $('#autoConnect').checked;
    saveSettingsNow();
    toast(state.settings.autoConnect ? 'Sẽ tự nhận link khi quay lại app' : 'Đã tắt tự nhận link');
  });
  $('#clearLinksBtn').addEventListener('click', () => {
    state.settings.links = [];
    saveSettingsNow();
    renderLinks();
    toast('Đã xoá danh sách link');
  });
  $('#diagnoseBtn').addEventListener('click', runDiagnose);
  $('#copyStatusCmdBtn').addEventListener('click', () => copyText(colabInfo().cmd_status, 'lệnh kiểm tra'));
  $('#copyRestartCmdBtn').addEventListener('click', () => copyText(colabInfo().cmd_restart, 'lệnh lấy link mới'));
  for (const sheet of $$('.sheet')) {
    sheet.addEventListener('click', (event) => {
      if (event.target === sheet) closeSheet(sheet);
    });
    for (const closer of sheet.querySelectorAll('[data-close]')) {
      closer.addEventListener('click', () => closeSheet(sheet));
    }
  }

  // prompt + gợi ý từ kho tag offline. Không chạy tìm kiếm/render khi IME đang ghép dấu.
  $('#prompt').addEventListener('compositionstart', () => {
    state.promptComposing = true;
    hideTagSuggestions();
  });
  $('#prompt').addEventListener('compositionend', () => {
    state.promptComposing = false;
    handlePromptInput();
  });
  $('#prompt').addEventListener('input', (event) => {
    if (state.promptComposing || event.isComposing) return;
    handlePromptInput();
  });
  $('#prompt').addEventListener('keydown', handlePromptSuggestionKeys);
  $('#prompt').addEventListener('blur', () => {
    clearTimeout(hideTagSuggestions.timer);
    hideTagSuggestions.timer = setTimeout(hideTagSuggestions, 140);
  });
  $('#quickTagRefresh').addEventListener('click', () => {
    state.quickTagOffset += 1;
    renderQuickTags();
  });
  $('#negative').addEventListener('input', scheduleSave);
  $('#normaliseBtn').addEventListener('click', normalisePromptField);
  $('#compactBtn').addEventListener('click', compactPromptField);
  $('#clearPromptBtn').addEventListener('click', () => {
    $('#prompt').value = '';
    hideTagSuggestions();
    renderQuickTags();
    updatePromptMeta();
    scheduleSave();
  });
  $('#rebuildNegativeBtn').addEventListener('click', rebuildNegative);

  // chế độ txt2img/img2img và ảnh init
  $('#modeTxt2Img').addEventListener('click', () => setGenerationMode('txt2img'));
  $('#modeImg2Img').addEventListener('click', () => setGenerationMode('img2img'));
  $('#img2imgPickBtn').addEventListener('click', () => $('#img2imgFile').click());
  $('#img2imgFile').addEventListener('change', async () => {
    const file = $('#img2imgFile').files?.[0];
    if (file) await setImg2ImgSource(file, { name: file.name });
    $('#img2imgFile').value = '';
  });
  $('#img2imgClearBtn').addEventListener('click', () => setImg2ImgSource(null));
  $('#img2imgDenoise').addEventListener('input', () => {
    state.settings.img2imgDenoise = Number($('#img2imgDenoise').value);
    updateImg2ImgControls();
    updatePromptMeta();
    scheduleSave();
  });
  $('#img2imgResizeMode').addEventListener('change', () => {
    state.settings.img2imgResizeMode = Number($('#img2imgResizeMode').value);
    saveSettingsNow();
  });

  // tham số nâng cao
  for (const id of ['seed', 'steps', 'cfg', 'batch', 'clipSkip', 'hrScale', 'hrSteps', 'denoise', 'hrUpscaler']) {
    $(`#${id}`).addEventListener('change', () => { readAdvanced(); updatePromptMeta(); });
  }
  $('#hires').addEventListener('change', () => { readAdvanced(); updatePromptMeta(); });

  // tạo ảnh
  $('#generateBtn').addEventListener('click', generate);
  $('#cancelBtn').addEventListener('click', cancelJob);
  $('#reuseSeedBtn').addEventListener('click', () => {
    if (state.lastSeed === null) return;
    state.settings.seed = state.lastSeed;
    $('#seed').value = String(state.lastSeed);
    saveSettingsNow();
    toast(`Đã khoá seed ${state.lastSeed}`);
  });
  $('#saveBtn').addEventListener('click', () => saveImageToDevice(state.results[0]));
  $('#shareBtn').addEventListener('click', () => shareImage(state.results[0]));

  // kho tag
  let tagTimer = null;
  const updateTagSearch = () => {
    state.tagQuery = $('#tagSearch').value;
    state.tagLimit = 60;
    clearTimeout(tagTimer);
    tagTimer = setTimeout(renderTagResults, 120);
  };
  $('#tagSearch').addEventListener('compositionstart', () => {
    state.tagComposing = true;
    clearTimeout(tagTimer);
  });
  $('#tagSearch').addEventListener('compositionend', () => {
    state.tagComposing = false;
    updateTagSearch();
  });
  $('#tagSearch').addEventListener('input', (event) => {
    if (state.tagComposing || event.isComposing) return;
    updateTagSearch();
  });
  $('#tagInsertBtn').addEventListener('click', insertSelectedTags);
  $('#tagClearBtn').addEventListener('click', () => {
    state.selected = [];
    renderTagResults();
    updateSelectionBar();
  });

  // phong cách
  let styleTimer = null;
  const updateStyleSearch = () => {
    state.styleQuery = $('#styleSearch').value;
    clearTimeout(styleTimer);
    styleTimer = setTimeout(renderStyleList, 120);
  };
  $('#styleSearch').addEventListener('compositionstart', () => {
    state.styleComposing = true;
    clearTimeout(styleTimer);
  });
  $('#styleSearch').addEventListener('compositionend', () => {
    state.styleComposing = false;
    updateStyleSearch();
  });
  $('#styleSearch').addEventListener('input', (event) => {
    if (state.styleComposing || event.isComposing) return;
    updateStyleSearch();
  });

  // cài đặt
  $('#apiUrl').addEventListener('change', () => connectTo($('#apiUrl').value));
  $('#apiUser').addEventListener('change', () => { state.settings.user = $('#apiUser').value.trim(); saveSettingsNow(); });
  $('#apiPass').addEventListener('change', () => { state.settings.pass = $('#apiPass').value; saveSettingsNow(); });
  $('#testBtn').addEventListener('click', testConnection);
  $('#setQuality').addEventListener('change', () => { state.settings.qualityPreset = $('#setQuality').value; saveSettingsNow(); });
  $('#setNegativePreset').addEventListener('change', () => {
    state.settings.negativePreset = $('#setNegativePreset').value;
    saveSettingsNow();
    rebuildNegative();
  });
  $('#setBlockWatermark').addEventListener('change', () => setBlockWatermark($('#setBlockWatermark').checked));
  $('#setSampler').addEventListener('change', () => { state.settings.sampler = $('#setSampler').value; saveSettingsNow(); });
  $('#setStylePreset').addEventListener('change', () => {
    const preset = (presets().style_presets || [])[Number($('#setStylePreset').value)];
    if (preset) appendTags(preset[1], preset[0]);
    $('#setStylePreset').value = '';
  });
  $('#installBtn').addEventListener('click', installApp);
  $('#clearGalleryBtn').addEventListener('click', async () => {
    if (!confirm('Xoá toàn bộ ảnh đã lưu trên máy?')) return;
    await store.clearImages();
    renderGallery();
    toast('Đã xoá thư viện ảnh');
  });

  // ảnh
  $('#imageReuseBtn').addEventListener('click', reuseImage);
  $('#imageImg2ImgBtn').addEventListener('click', useViewImageForImg2Img);
  $('#imageUpscaleBtn').addEventListener('click', upscaleCurrentImage);
  $('#upscaleCancelBtn').addEventListener('click', cancelUpscale);
  $('#imageSaveBtn').addEventListener('click', async () => {
    const item = state.viewId ? await store.getImage(state.viewId) : null;
    if (item) saveImageToDevice(item);
  });
  $('#imageShareBtn').addEventListener('click', async () => {
    const item = state.viewId ? await store.getImage(state.viewId) : null;
    if (item) shareImage(item);
  });
  $('#imageDeleteBtn').addEventListener('click', async () => {
    if (!state.viewId) return;
    await store.deleteImage(state.viewId);
    closeSheet($('#sheetImage'));
    renderGallery();
    toast('Đã xoá ảnh');
  });

  // PWA install prompt
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    state.installEvent = event;
    $('#installBtn').classList.remove('hidden');
  });

  window.addEventListener('online', () => pingServer());
  window.addEventListener('offline', () => setConn('mất mạng', 'bad'));
}

function showTab(name) {
  document.body.dataset.tab = name;
  if (name !== 'create') hideTagSuggestions();
  for (const tab of $$('.tab')) tab.classList.toggle('active', tab.id === `tab-${name}`);
  for (const button of $$('.tab-btn')) {
    const active = button.dataset.tab === name;
    button.classList.toggle('active', active);
    button.setAttribute('aria-current', active ? 'page' : 'false');
  }
  if (name === 'gallery') renderGallery();
  if (name === 'tags' && state.data) renderTagResults();
  if (name === 'server') renderServerTab();
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
}

function openSheet(selector) {
  const sheet = $(selector);
  sheet.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  if (selector === '#sheetSettings') fillSettingsForm();
}

function closeSheet(sheet) {
  sheet.classList.add('hidden');
  if (sheet.id === 'sheetImage' && state.viewUrl) {
    URL.revokeObjectURL(state.viewUrl);
    state.viewUrl = '';
  }
  if (!$$('.sheet').some((item) => !item.classList.contains('hidden'))) {
    document.body.style.overflow = '';
  }
}

// ------------------------------------------------------------------ cài đặt <-> form
const ADVANCED_FIELDS = { seed: 'seed', steps: 'steps', cfg: 'cfg', batch: 'batch', clipSkip: 'clipSkip', hrScale: 'hrScale', hrSteps: 'hrSteps', denoise: 'denoise' };

function applySettingsToForm() {
  const settings = state.settings;
  $('#apiUrl').value = settings.apiUrl || '';
  $('#apiUser').value = settings.user || '';
  $('#apiPass').value = settings.pass || '';
  for (const [id, key] of Object.entries(ADVANCED_FIELDS)) {
    const node = $(`#${id}`);
    if (node) node.value = String(settings[key]);
  }
  $('#hires').checked = Boolean(settings.hires);
  $('#hrUpscaler').value = settings.hrUpscaler || 'RealESRGAN_x4plus_anime_6B';
  $('#prompt').value = settings.prompt || '';
  $('#negative').value = settings.negative || buildNegativeFor(settings.rating);
  setGenerationMode(settings.generationMode, { save: false });
  updateImg2ImgControls();
  updateSelectionBar();
}

function setGenerationMode(mode, { save = true } = {}) {
  const selected = mode === 'img2img' ? 'img2img' : 'txt2img';
  state.settings.generationMode = selected;
  const isImg2Img = selected === 'img2img';
  for (const [id, active] of [['#modeTxt2Img', !isImg2Img], ['#modeImg2Img', isImg2Img]]) {
    $(id).classList.toggle('active', active);
    $(id).setAttribute('aria-selected', String(active));
  }
  $('#img2imgSourceCard').classList.toggle('hidden', !isImg2Img);
  $('#hiresFields').classList.toggle('hidden', isImg2Img);
  $('#generateBtn').textContent = isImg2Img ? '🎨 Tạo từ ảnh' : '🖼️ Tạo ảnh';
  $('#prompt').placeholder = isImg2Img
    ? 'Mô tả nét muốn giữ/thay đổi: tóc dài, áo dài, ánh sáng…'
    : 'tóc dài, áo dài, ánh sáng… hoặc 1girl, long_hair, smile…';
  if (save) saveSettingsNow();
  updatePromptMeta();
}

function updateImg2ImgControls() {
  const value = Number(state.settings.img2imgDenoise);
  $('#img2imgDenoise').value = String(Number.isFinite(value) ? value : 0.55);
  $('#img2imgDenoiseValue').textContent = `${Math.round(Number($('#img2imgDenoise').value) * 100)}%`;
  $('#img2imgResizeMode').value = String(state.settings.img2imgResizeMode ?? 1);
}

async function setImg2ImgSource(blob, { name = '', sourceId = '' } = {}) {
  if (blob) {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(blob.type)) {
      toast('Chỉ hỗ trợ ảnh PNG, JPEG hoặc WebP.', { error: true });
      return false;
    }
    if (blob.size > 20 * 1024 * 1024) {
      toast('Ảnh gốc vượt 20 MiB; hãy chọn ảnh nhỏ hơn.', { error: true, ms: 5000 });
      return false;
    }
  }
  if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
  state.source = blob || null;
  state.sourceUrl = blob ? URL.createObjectURL(blob) : '';
  state.sourceName = name || (blob ? 'Ảnh đã chọn' : '');
  state.sourceId = sourceId || '';
  $('#img2imgPreview').classList.toggle('hidden', !blob);
  $('#img2imgEmpty').classList.toggle('hidden', Boolean(blob));
  $('#img2imgClearBtn').classList.toggle('hidden', !blob);
  if (blob) $('#img2imgPreview').src = state.sourceUrl;
  else $('#img2imgPreview').removeAttribute('src');
  $('#img2imgSourceName').textContent = blob ? `${state.sourceName} · ${formatBytes(blob.size)}` : '';
  return true;
}

function fillSettingsForm() {
  if (!$('#setQuality').options.length && state.data) fillSelects();
  $('#setQuality').value = state.settings.qualityPreset;
  $('#setNegativePreset').value = state.settings.negativePreset;
  $('#setBlockWatermark').checked = state.settings.blockWatermark !== false;
  $('#setSampler').value = state.settings.sampler;
}

function fillSelects() {
  const quality = Object.keys(presets().quality || {});
  const negative = Object.keys(presets().negative || {});
  const samplers = presets().samplers || [];
  const stylePresets = presets().style_presets || [];

  $('#setQuality').replaceChildren(...quality.map((name) => h('option', { value: name }, name)));
  $('#setNegativePreset').replaceChildren(...negative.map((name) => h('option', { value: name }, name)));
  $('#setSampler').replaceChildren(...samplers.map((name) => h('option', { value: name }, name)));
  $('#setStylePreset').replaceChildren(
    h('option', { value: '' }, '— chọn công thức để thêm tag —'),
    ...stylePresets.map((preset, index) => h('option', { value: index }, preset[0])),
  );

  if (!quality.includes(state.settings.qualityPreset) && quality.length) {
    state.settings.qualityPreset = quality[0];
  }
  if (!negative.includes(state.settings.negativePreset) && negative.length) {
    state.settings.negativePreset = negative.find((name) => name.includes('ngắn')) || negative[0];
  }
  if (!samplers.includes(state.settings.sampler) && samplers.length) {
    state.settings.sampler = samplers[0];
  }
}

function readAdvanced() {
  const settings = state.settings;
  for (const [id, key] of Object.entries(ADVANCED_FIELDS)) {
    const node = $(`#${id}`);
    if (!node) continue;
    const value = Number(node.value);
    if (Number.isFinite(value)) settings[key] = value;
  }
  settings.seed = Number.isFinite(Number($('#seed').value)) ? Number($('#seed').value) : -1;
  settings.hires = $('#hires').checked;
  settings.hrUpscaler = $('#hrUpscaler').value;
  saveSettingsNow();
}

function scheduleSave() {
  clearTimeout(scheduleSave.timer);
  scheduleSave.timer = setTimeout(saveSettingsNow, 600);
}

function saveSettingsNow() {
  state.settings.prompt = $('#prompt').value;
  state.settings.negative = $('#negative').value;
  store.saveSettings(state.settings);
}

// ------------------------------------------------------------------ chips
function renderSizeChips() {
  const list = sizePresets();
  const box = $('#sizeChips');
  box.replaceChildren(...list.map(([label, size], index) => h('button', {
    class: `chip${index === state.settings.sizeIndex ? ' active' : ''}`,
    type: 'button',
    text: `${label.split(' (')[0]} · ${size[0]}×${size[1]}`,
    onclick: () => {
      state.settings.sizeIndex = index;
      renderSizeChips();
      updatePromptMeta();
      saveSettingsNow();
    },
  })));
}

function renderRatingChips() {
  const list = presets().ratings || [];
  const short = { general: 'An toàn', sensitive: 'Nhạy cảm', questionable: 'Đáng ngờ', explicit: '18+' };
  const box = $('#ratingChips');
  box.replaceChildren(...list.map((item) => h('button', {
    class: `chip${item.id === state.settings.rating ? ' active' : ''}`,
    type: 'button',
    text: short[item.id] || item.label,
    onclick: () => {
      state.settings.rating = item.id;
      renderRatingChips();
      rebuildNegative();
      updatePromptMeta();
      saveSettingsNow();
    },
  })));
}

function renderStylePresets() {
  const box = $('#stylePresets');
  const list = presets().style_presets || [];
  if (!list.length) {
    box.replaceChildren(h('span', { class: 'hint' }, 'Chưa có dữ liệu phong cách.'));
    return;
  }
  box.replaceChildren(...list.map(([name, tags, note]) => h('button', {
    class: 'chip',
    type: 'button',
    text: name,
    title: note,
    onclick: () => {
      appendTags(tags, name);
      closeSheet($('#sheetStyle'));
    },
  })));
}

function renderStyleGroups() {
  if (!state.data) return;
  const groups = state.data.styleGroups();
  const box = $('#styleGroups');
  box.replaceChildren(h('button', {
    class: `chip${state.styleGroup === null ? ' active' : ''}`,
    type: 'button',
    text: `Tất cả (${state.data.styles.length})`,
    onclick: () => { state.styleGroup = null; renderStyleGroups(); renderStyleList(); },
  }), ...groups.map((group) => h('button', {
    class: `chip${state.styleGroup === group ? ' active' : ''}`,
    type: 'button',
    text: group,
    onclick: () => { state.styleGroup = group; renderStyleGroups(); renderStyleList(); },
  })));
}

function renderStyleList() {
  if (!state.data) return;
  const items = state.data.searchStyles(state.styleQuery, { limit: 120, group: state.styleGroup });
  const box = $('#styleList');
  if (!items.length) {
    box.replaceChildren(h('p', { class: 'hint' }, 'Không tìm thấy phong cách phù hợp.'));
    return;
  }
  box.replaceChildren(...items.map((item) => h('button', {
    class: 'tag-row',
    type: 'button',
    onclick: () => {
      appendTags([item.tag], item.tag);
    },
  }, h('span', { class: 'tag-main' },
    h('span', { class: 'tag-en' }, item.tag),
    h('span', { class: 'tag-vi' }, item.vi || '—'),
  ), h('span', { class: 'tag-count' }, item.group))));
}

// ------------------------------------------------------------------ kho tag
function renderTagResults() {
  if (!state.data) {
    $('#tagResults').replaceChildren(h('p', { class: 'hint' }, 'Chưa nạp được kho tag.'));
    return;
  }
  renderTagFilters();
  const rows = state.data.search(state.tagQuery, {
    limit: state.tagLimit,
    group: state.tagGroup === 'all' ? null : state.tagGroup,
  });
  const selectedKeys = new Set(state.selected.map((tag) => core.normKey(tag)));
  const groupIndex = state.data.resolveGroup(state.tagGroup);
  const groupLabel = groupIndex === null ? 'Tất cả nhóm'
    : state.data.groupLabels[groupIndex] || state.tagGroup;
  $('#tagResultMeta').textContent = `${rows.length === state.tagLimit ? 'Hiển thị ' : ''}${rows.length} tag · ${groupLabel}`;
  const box = $('#tagResults');
  const children = rows.map((row) => {
    const isSelected = selectedKeys.has(core.normKey(row.tag));
    return h('button', {
      class: `tag-row${isSelected ? ' selected' : ''}`,
      type: 'button',
      onclick: () => toggleTag(row.tag),
    },
    h('span', { class: 'tag-main' },
      h('span', { class: 'tag-en' }, row.tag),
      h('span', { class: 'tag-vi' }, row.vi || '—'),
    ),
    h('span', { class: 'tag-count' },
      TagData.formatCount(row.count),
      h('span', { class: 'tag-badge' }, shortGroup(row.groupLabel))),
    );
  });
  if (!rows.length) {
    children.push(h('p', { class: 'hint' }, 'Không tìm thấy tag. Thử bỏ dấu hoặc dùng từ tiếng Anh.'));
  }
  if (rows.length === state.tagLimit) {
    children.push(h('button', {
      class: 'chip',
      type: 'button',
      text: 'Xem thêm',
      onclick: () => { state.tagLimit += 60; renderTagResults(); },
    }));
  }
  box.replaceChildren(...children);
  updateSelectionBar();
}

function shortGroup(label) {
  return String(label || '').split(' (')[0].replace('&', '/').slice(0, 14);
}

function renderTagFilters() {
  if (!state.data) return;
  const box = $('#tagFilters');
  if (box.dataset.ready === '1') return;
  const groups = state.data.browseGroups;
  box.replaceChildren(h('button', {
    class: `chip${state.tagGroup === 'all' || state.tagGroup === null ? ' active' : ''}`,
    type: 'button',
    text: 'Tất cả',
    onclick: () => { state.tagGroup = 'all'; markFilters(); renderTagResults(); },
  }), ...groups.map((group) => h('button', {
    class: 'chip',
    type: 'button',
    text: state.data.groupLabels[state.data.groups.indexOf(group)] || group,
    'data-group': group,
    onclick: () => { state.tagGroup = group; markFilters(); renderTagResults(); },
  })));
  box.dataset.ready = '1';
  markFilters();
}

function markFilters() {
  for (const chip of $$('#tagFilters .chip')) {
    const group = chip.dataset.group;
    const active = group ? group === state.tagGroup : (state.tagGroup === 'all' || state.tagGroup === null);
    chip.classList.toggle('active', active);
  }
}

function toggleTag(tag) {
  const key = core.normKey(tag);
  const index = state.selected.findIndex((item) => core.normKey(item) === key);
  if (index >= 0) state.selected.splice(index, 1);
  else state.selected.push(tag);
  renderTagResults();
}

function updateSelectionBar() {
  const bar = $('#tagSelBar');
  if (!state.selected.length) {
    bar.classList.add('hidden');
    return;
  }
  bar.classList.remove('hidden');
  $('#tagSelText').textContent = `Đã chọn ${state.selected.length} tag`;
}

function insertSelectedTags() {
  if (!state.selected.length) return;
  appendTags(state.selected, `${state.selected.length} tag`);
  state.selected = [];
  updateSelectionBar();
  renderTagResults();
  showTab('create');
}

// ------------------------------------------------------------------ prompt + gợi ý tag offline
function renderQuickTags() {
  const box = $('#quickTagList');
  if (!box) return;
  if (!state.data) {
    box.replaceChildren(h('span', { class: 'hint' }, 'Kho tag chưa sẵn sàng.'));
    return;
  }
  const present = new Set(core.parseTags($('#prompt').value).map((piece) => core.normKey(piece.tag)));
  const groups = ['subject', 'appearance', 'clothing', 'expression', 'pose', 'background', 'camera'];
  const chips = [];
  for (const group of groups) {
    const items = state.data.quick[group] || [];
    if (!items.length) continue;
    // Bỏ tag đầu nhóm ngoại hình để gợi ý mặc định bắt đầu bằng long_hair.
    const start = (state.quickTagOffset + (group === 'appearance' ? 1 : 0)) % items.length;
    for (let step = 0; step < items.length; step += 1) {
      const [tag, vi] = items[(start + step) % items.length];
      if (present.has(core.normKey(tag))) continue;
      const groupIndex = state.data.groups.indexOf(group);
      chips.push(h('button', {
        class: 'chip quick-tag',
        type: 'button',
        text: tag,
        title: `${vi || tag} · ${state.data.groupLabels[groupIndex] || group}`,
        onclick: () => appendTags([tag], vi || tag),
      }));
      break;
    }
  }
  box.replaceChildren(...(chips.length ? chips : [h('span', { class: 'hint' }, 'Các gợi ý đã có trong prompt.')]));
}

function renderTagLibraryMeta() {
  if (!state.data) return;
  $('#tagDataMeta').textContent = `${state.data.rows.length.toLocaleString('vi-VN')} tag · `
    + `${state.data.browseGroups.length} nhóm · tìm Anh/Việt không cần mạng`;
}

function handlePromptInput() {
  updatePromptMeta();
  scheduleSave();
  schedulePromptSuggestions();
  renderQuickTags();
}

function schedulePromptSuggestions() {
  clearTimeout(schedulePromptSuggestions.timer);
  clearTimeout(hideTagSuggestions.timer);
  schedulePromptSuggestions.timer = setTimeout(renderPromptSuggestions, 80);
}

function hideTagSuggestions() {
  clearTimeout(schedulePromptSuggestions.timer);
  $('#tagSuggest').classList.add('hidden');
  $('#tagSuggestList').replaceChildren();
  state.suggestions = [];
  state.suggestionIndex = -1;
}

function renderPromptSuggestions() {
  if (!state.data) {
    hideTagSuggestions();
    return;
  }
  const textarea = $('#prompt');
  const fragment = core.activeTagFragment(textarea.value, textarea.selectionStart);
  if (!fragment.query) {
    hideTagSuggestions();
    return;
  }
  const present = new Set(core.parseTags(textarea.value).map((piece) => core.normKey(piece.tag)));
  const rows = state.data.search(fragment.query, { limit: 20 })
    .filter((row) => !present.has(core.normKey(row.tag)))
    .slice(0, 6);
  if (!rows.length) {
    hideTagSuggestions();
    return;
  }
  state.suggestions = rows;
  state.suggestionIndex = 0;
  $('#tagSuggestList').replaceChildren(...rows.map((row, index) => h('button', {
    class: `suggestion-row${index === 0 ? ' active' : ''}`,
    type: 'button',
    role: 'option',
    'aria-selected': index === 0 ? 'true' : 'false',
    onpointerdown: (event) => event.preventDefault(),
    onclick: () => applyPromptSuggestion(index),
  },
  h('span', { class: 'suggestion-main' },
    h('strong', { text: row.tag }),
    h('span', { text: row.vi || row.groupLabel }),
  ),
  h('span', { class: 'suggestion-count', text: TagData.formatCount(row.count) }),
  )));
  $('#tagSuggest').classList.remove('hidden');
}

function applyPromptSuggestion(index) {
  const row = state.suggestions[index];
  if (!row) return;
  const textarea = $('#prompt');
  const replaced = core.replaceActiveTag(textarea.value, textarea.selectionStart, row.tag);
  textarea.value = replaced.text;
  hideTagSuggestions();
  textarea.focus();
  textarea.setSelectionRange(replaced.caret, replaced.caret);
  updatePromptMeta();
  saveSettingsNow();
  renderQuickTags();
}

function markActiveSuggestion() {
  $$('#tagSuggestList .suggestion-row').forEach((row, index) => {
    const active = index === state.suggestionIndex;
    row.classList.toggle('active', active);
    row.setAttribute('aria-selected', active ? 'true' : 'false');
    if (active) row.scrollIntoView({ block: 'nearest' });
  });
}

function handlePromptSuggestionKeys(event) {
  // Enter/keyCode 229 của bàn phím Việt dùng để chốt ký tự, không phải chọn gợi ý.
  if (state.promptComposing || event.isComposing || event.keyCode === 229) return;
  if ($('#tagSuggest').classList.contains('hidden') || !state.suggestions.length) return;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    const direction = event.key === 'ArrowDown' ? 1 : -1;
    state.suggestionIndex = (state.suggestionIndex + direction + state.suggestions.length)
      % state.suggestions.length;
    markActiveSuggestion();
  } else if (event.key === 'Enter' && state.suggestionIndex >= 0) {
    event.preventDefault();
    applyPromptSuggestion(state.suggestionIndex);
  } else if (event.key === 'Escape' || event.key === 'Tab') {
    hideTagSuggestions();
  }
}

function appendTags(tags, label = '') {
  hideTagSuggestions();
  const textarea = $('#prompt');
  const existing = core.parseTags(textarea.value);
  const present = new Set(existing.map((piece) => core.normKey(piece.tag)));
  const added = [];
  for (const tag of tags) {
    const key = core.normKey(tag);
    if (!key || present.has(key)) continue;
    present.add(key);
    added.push(tag);
  }
  if (!added.length) {
    toast(`Tag đã có trong prompt${label ? ` (${label})` : ''}`);
    return;
  }
  const prefix = textarea.value.trim() ? `${textarea.value.trim().replace(/,\s*$/, '')}, ` : '';
  textarea.value = `${prefix}${added.join(', ')}`;
  renderQuickTags();
  updatePromptMeta();
  saveSettingsNow();
  toast(`Đã thêm ${added.length} tag${label ? ` · ${label}` : ''}`);
}

/** Nhóm tag chặn chữ ký/watermark/logo Patreon; rỗng khi người dùng đã tắt công tắc. */
function watermarkGuard() {
  if (state.settings.blockWatermark === false) return '';
  return presets().anti_watermark || core.ANTI_WATERMARK;
}

/** Negative lấy từ nơi khác (ảnh cũ trong Thư viện) vẫn phải có nhóm chặn nếu đang bật. */
function withWatermarkGuard(text) {
  const value = String(text ?? '');
  const guard = watermarkGuard();
  return value.trim() && guard ? core.mergeTags(value, guard) : value;
}

/**
 * Di trú một lần: app lưu nguyên ô negative vào máy, nên người đã dùng bản cũ sẽ không
 * bao giờ nhận được nhóm tag chặn watermark nếu chỉ đổi preset. Nối phần còn thiếu vào
 * negative đã lưu (giữ nguyên phần người dùng tự viết) rồi đánh dấu để không làm lại.
 */
function migrateWatermarkGuard() {
  const settings = state.settings;
  if (Number(settings.watermarkGuard) >= 1) return false;
  settings.watermarkGuard = 1;
  const before = String(settings.negative || '');
  const after = withWatermarkGuard(before);
  settings.negative = after;
  store.saveSettings(settings);
  return after !== before;
}

function buildNegativeFor(ratingId) {
  const rating = ratingById(ratingId);
  return core.buildNegative({
    preset: (presets().negative || {})[state.settings.negativePreset] || '',
    guard: watermarkGuard(),
    ratingNegative: rating.negative || [],
    extra: state.settings.negativeExtra || '',
  });
}

/** Bật: nối nhóm chặn vào negative hiện có. Tắt: gỡ đúng các tag đó, không đụng phần khác. */
function setBlockWatermark(enabled) {
  state.settings.blockWatermark = Boolean(enabled);
  const field = $('#negative');
  const tags = presets().anti_watermark || core.ANTI_WATERMARK;
  if (enabled) {
    field.value = field.value.trim() ? core.mergeTags(field.value, tags)
      : buildNegativeFor(state.settings.rating);
  } else {
    field.value = core.removeTags(field.value, tags);
  }
  updatePromptMeta();
  saveSettingsNow();
  toast(enabled ? 'Đã bật chặn watermark / chữ ký / logo Patreon'
    : 'Đã tắt chặn watermark — model có thể tự vẽ chữ ký, logo');
}

function rebuildNegative() {
  $('#negative').value = buildNegativeFor(state.settings.rating);
  saveSettingsNow();
}

/** Chỉ chuyển cụm có bản dịch chính xác; câu chưa biết được giữ nguyên, không đoán. */
function translateKnownPrompt(text) {
  if (!state.data) return String(text ?? '');
  return core.parseTags(text).map((piece) => core.renderTag(
    state.data.englishOf(piece.tag),
    piece.weight,
  )).join(', ');
}

function normalisePromptField() {
  const text = translateKnownPrompt($('#prompt').value);
  if (!text.trim()) {
    toast('Chưa có prompt để chuẩn hoá', { error: true });
    return;
  }
  $('#prompt').value = core.normalisePrompt(text, {
    quality: (presets().quality || {})[state.settings.qualityPreset] || '',
    ratingPositive: ratingById(state.settings.rating).positive || [],
    groupOf,
    dropDuplicates: true,
  });
  updatePromptMeta();
  saveSettingsNow();
  toast('Đã chuyển cụm Việt đã biết, sắp xếp nhóm và thêm tag chất lượng');
}

function compactPromptField() {
  const pieces = core.dedupePieces(core.parseTags(translateKnownPrompt($('#prompt').value)));
  $('#prompt').value = pieces.map((piece) => core.renderTag(piece.tag, piece.weight)).join(', ');
  updatePromptMeta();
  saveSettingsNow();
  toast('Đã bỏ tag trùng nghĩa');
}

/** Prompt gửi đi: thêm tag chất lượng + phân loại nếu người dùng chưa có. */
function finalPositive() {
  const text = translateKnownPrompt($('#prompt').value.trim());
  if (!text) return '';
  const present = new Set(core.parseTags(text).map((piece) => core.normKey(piece.tag)));
  const wanted = [
    (presets().quality || {})[state.settings.qualityPreset] || '',
    ...(ratingById(state.settings.rating).positive || []),
  ].filter(Boolean).join(', ');
  const prefix = core.parseTags(wanted)
    .filter((piece) => !present.has(core.normKey(piece.tag)))
    .map((piece) => core.renderTag(piece.tag, piece.weight));
  return [prefix.join(', '), text].filter(Boolean).join(', ');
}

function updatePromptMeta() {
  const text = $('#prompt').value;
  const pieces = core.parseTags(text);
  const tokens = core.estimateTokens(text);
  const advice = core.tokenAdvice(tokens);
  const info = $('#tokenInfo');
  info.textContent = `${pieces.length} tag · ${tokens} token · ${advice.label}`;
  info.className = `token-info ${advice.level}`;
  info.title = advice.text;

  const overrides = currentOverrides();
  const warnings = core.payloadWarnings(overrides);
  if (state.settings.generationMode === 'img2img') {
    warnings.push(...core.payloadWarnings({
      ...overrides, init_images: state.source ? ['selected'] : [],
      denoising_strength: state.settings.img2imgDenoise,
    }));
  }
  const calling = core.tagsIn(text, presets().anti_watermark || core.ANTI_WATERMARK);
  if (calling.length) {
    warnings.push(`Prompt đang tự gọi chữ/logo lên ảnh: ${calling.join(', ')} — xoá các tag này nếu không muốn.`);
  }
  const box = $('#promptWarn');
  if (warnings.length) {
    box.textContent = `⚠️ ${warnings.join(' · ')}`;
    box.classList.remove('hidden');
  } else {
    box.classList.add('hidden');
  }
}

function currentOverrides() {
  const settings = state.settings;
  const [, size] = currentSize();
  return {
    steps: settings.steps,
    cfg_scale: settings.cfg,
    sampler_name: settings.sampler,
    width: size[0],
    height: size[1],
    batch_size: settings.batch,
    seed: settings.seed,
    enable_hr: settings.generationMode !== 'img2img' && settings.hires,
    hr_scale: settings.hrScale,
    hr_second_pass_steps: settings.hrSteps,
    hr_upscaler: settings.hrUpscaler,
    denoising_strength: settings.denoise,
    clip_skip: settings.clipSkip,
  };
}

// ------------------------------------------------------------------ sinh ảnh
async function generate() {
  if (state.busy) return;
  const isImg2Img = state.settings.generationMode === 'img2img';
  const source = isImg2Img ? state.source : null;
  const sourceId = state.sourceId;
  if (isImg2Img && !source) {
    setStatus('Chọn ảnh gốc từ máy hoặc Thư viện trước khi dùng img2img.', { error: true });
    toast('Chưa chọn ảnh gốc img2img', { error: true });
    $('#img2imgPickBtn').focus();
    return;
  }
  const positive = finalPositive();
  if (!positive) {
    toast('Nhập prompt trước đã', { error: true });
    $('#prompt').focus();
    return;
  }
  const negative = translateKnownPrompt($('#negative').value.trim())
    || buildNegativeFor(state.settings.rating);

  const submissionParams = currentOverrides();
  const payload = core.buildPayload({
    positive,
    negative,
    defaults: presets().defaults || {},
    overrides: submissionParams,
  });
  if (isImg2Img) {
    payload.init_images = ['pending-image-encoding'];
    payload.denoising_strength = Number(state.settings.img2imgDenoise);
    payload.resize_mode = Number(state.settings.img2imgResizeMode);
    payload.include_init_images = false;
    delete payload.enable_hr;
  }
  const errors = core.payloadErrors(payload);
  if (errors.length) {
    setStatus(`⚠️ ${errors.join(' ')}`, { error: true });
    toast(errors[0], { error: true, ms: 5000 });
    return;
  }

  state.busy = true;
  state.controller = new AbortController();
  renderServerTab();
  $('#generateBtn').classList.add('hidden');
  $('#cancelBtn').classList.remove('hidden');
  setProgress(4);
  setStatus('⏳ Đang gửi yêu cầu tới Forge…');
  setConn('đang chạy…', '');

  try {
    if (isImg2Img) {
      setStatus('⏳ Đang đọc ảnh gốc; không tải ảnh lại từ object URL…');
      payload.init_images = [await blobToBase64(source)];
    }
    const api = client();
    state.activeClient = api;
    const run = isImg2Img ? api.img2img.bind(api) : api.txt2img.bind(api);
    const result = await run(payload, {
      signal: state.controller.signal,
      onJob: (job) => { state.activeJobId = job.job_id; },
      onProgress: (info, elapsed) => {
        setProgress((Number(info.progress) || 0) * 100);
        setStatus(core.progressText(info, elapsed));
      },
      onDownload: ({ loaded, total, index, count }) => {
        const percent = total ? (loaded / total) * 100 : 95;
        setProgress(percent);
        setStatus(`⬇️ Đang tải file ${index + 1}/${count}: ${formatBytes(loaded)}/${formatBytes(total)} · không chạy lại job`);
      },
    });
    const media = result.images.map((blob, index) => {
      const extension = ({ 'image/jpeg': 'jpg', 'image/webp': 'webp' })[blob.type] || 'png';
      return {
        blob,
        url: URL.createObjectURL(blob),
        name: `anime3-${core.seedFromInfo(result.info) ?? Date.now()}-${index}.${extension}`,
      };
    });
    revokeResultUrls();
    state.results = media;
    state.lastInfo = result.info;
    state.lastSeed = core.seedFromInfo(result.info);
    renderResult({ ...result, images: media });
    setProgress(100);
    setStatus(`✅ Job ${result.jobId.slice(0, 8)} · xong sau ${core.formatDuration(result.elapsed)}`
      + `${state.lastSeed !== null ? ` · seed ${state.lastSeed}` : ''}`);
    if (result.storageWarning) toast(result.storageWarning, { error: true, ms: 6000 });
    await saveResultImages({
      ...result,
      images: media,
      params: {
        ...submissionParams,
        operation: isImg2Img ? 'img2img' : 'txt2img',
        ...(isImg2Img ? {
          denoising_strength: payload.denoising_strength,
          resize_mode: payload.resize_mode,
          source_id: sourceId,
        } : {}),
      },
    });
    pingServer();
  } catch (error) {
    if (error?.name === 'AbortError') {
      setStatus('⛔ Đã huỷ job.');
      setProgress(null);
    } else {
      const message = error instanceof ForgeError ? error.message : `Lỗi: ${error.message}`;
      setStatus(message, { error: true });
      setProgress(null);
      toast(message, { error: true, ms: 5000 });
      setConn('lỗi kết nối', 'bad');
    }
  } finally {
    state.busy = false;
    state.controller = null;
    state.activeClient = null;
    state.activeJobId = '';
    $('#generateBtn').classList.remove('hidden');
    $('#cancelBtn').classList.add('hidden');
    renderServerTab();
  }
}

async function cancelJob() {
  if (!state.busy) return;
  setStatus('⛔ Đang huỷ…');
  if (state.activeClient && state.activeJobId) {
    await state.activeClient.cancelJob(state.activeJobId);
  } else {
    await client().interrupt();
  }
  state.controller?.abort();
}

function revokeResultUrls() {
  for (const item of state.results) {
    if (item?.url) URL.revokeObjectURL(item.url);
  }
}

function renderResult(result) {
  const card = $('#resultCard');
  card.classList.remove('hidden');
  const info = result.info || {};
  const seed = core.seedFromInfo(info);
  $('#resultMeta').textContent = [
    `seed ${seed ?? '?'}`,
    `${info.width || '?'}×${info.height || '?'}`,
    `${core.formatDuration(result.elapsed)}`,
    info.sampler_name ? `${info.sampler_name} · ${info.steps || '?'} bước` : '',
  ].filter(Boolean).join(' · ');
  $('#resultImages').replaceChildren(...result.images.map((item) => h('img', {
    src: item.url,
    alt: 'Ảnh vừa tạo',
    onclick: () => openImage(null, item.url, $('#resultMeta').textContent),
  })));
  $('#resultCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Ảnh thu nhỏ cho lưới thư viện (JPEG ~420 px). Không có canvas/ảnh thì trả '' —
 * thư viện vẫn mở được ảnh gốc, chỉ mất ảnh xem trước.
 */
async function makeThumb(image, max = 420) {
  try {
    let bitmap;
    if (typeof createImageBitmap === 'function') {
      const blob = image?.blob || await (await fetch(image)).blob();
      bitmap = await Promise.race([
        createImageBitmap(blob),
        new Promise((resolve) => setTimeout(() => resolve(null), 2500)),
      ]);
    }
    if (!bitmap) return '';
    const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext && canvas.getContext('2d');
    if (!context) return '';
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    if (bitmap.close) bitmap.close();
    return canvas.toDataURL('image/jpeg', 0.72);
  } catch (error) {
    return '';
  }
}

async function saveResultImages(result) {
  const reuse = core.reuseFromInfo(result.info) || {};
  for (const [index, image] of result.images.entries()) {
    try {
      await store.addImage({
        blob: image.blob,
        name: image.name,
        mime: image.blob.type,
        thumb: await makeThumb(image),
        prompt: reuse.prompt || $('#prompt').value,
        negative: reuse.negative || $('#negative').value,
        seed: reuse.seed,
        info: { ...result.info, operation: result.params?.operation || 'txt2img' },
        params: result.params || currentOverrides(),
        index,
      });
    } catch (error) {
      console.warn('Không lưu được ảnh vào thư viện', error);
    }
  }
  renderGallery();
}

// ------------------------------------------------------------------ thư viện
async function renderGallery() {
  const items = await store.listImages({ limit: 60 });
  const box = $('#gallery');
  $('#galleryEmpty').classList.toggle('hidden', items.length > 0);
  box.replaceChildren(...items.map((item) => h('button', {
    type: 'button',
    onclick: () => openItem(item),
  }, item.thumb
    ? h('img', { src: item.thumb, alt: item.prompt || 'Ảnh đã tạo', loading: 'lazy' })
    : h('div', { class: 'thumb-placeholder', text: '🖼' }))));
}

function describeItem(item) {
  const when = item.createdAt ? new Date(item.createdAt).toLocaleString('vi-VN') : '';
  return [
    when,
    item.seed !== null && item.seed !== undefined ? `seed ${item.seed}` : '',
    (item.prompt || '').slice(0, 90) + ((item.prompt || '').length > 90 ? '…' : ''),
  ].filter(Boolean).join(' · ');
}

/** Mở một mục: lấy Blob từ IndexedDB rồi tạo object URL có vòng đời rõ ràng. */
async function openItem(item) {
  const full = await store.getImage(item.id);
  if (!full) {
    toast('Không đọc được ảnh này', { error: true });
    renderGallery();
    return;
  }
  if (state.viewUrl) URL.revokeObjectURL(state.viewUrl);
  state.viewUrl = full.blob ? URL.createObjectURL(full.blob) : '';
  openImage(item.id, state.viewUrl || full.dataUrl, describeItem(item));
}

async function openImage(id, dataUrl, meta) {
  state.viewId = id;
  $('#imageView').src = dataUrl;
  $('#imageMeta').textContent = meta || '';
  $('#imageSaveLocation').textContent = 'Nơi xuất trên Android 10+: Pictures/Anime3. Ảnh chưa xuất vẫn nằm trong bộ nhớ riêng của app.';
  if (!state.busy) $('#upscaleStatus').textContent = 'Bản mới được lưu riêng trong Thư viện; không tạo lại ảnh bằng prompt.';
  $('#imageReuseBtn').classList.toggle('hidden', !id);
  $('#imageDeleteBtn').classList.toggle('hidden', !id);
  openSheet('#sheetImage');
}

async function reuseImage() {
  if (!state.viewId) return;
  const item = await store.getImage(state.viewId);
  if (!item) return;
  $('#prompt').value = item.prompt || '';
  $('#negative').value = withWatermarkGuard(item.negative || '');
  if (item.seed !== null && item.seed !== undefined) {
    state.settings.seed = item.seed;
    $('#seed').value = String(item.seed);
  }
  updatePromptMeta();
  saveSettingsNow();
  closeSheet($('#sheetImage'));
  showTab('create');
  toast('Đã nạp lại prompt và seed');
}

async function useViewImageForImg2Img() {
  if (state.busy) {
    toast('Đang có job chạy; chờ hoàn tất trước khi đổi ảnh init.', { error: true });
    return;
  }
  const item = state.viewId ? await store.getImage(state.viewId) : null;
  const blob = item?.blob || (!state.viewId ? state.results[0]?.blob : null)
    || await (await fetch($('#imageView').src)).blob();
  const accepted = await setImg2ImgSource(blob, {
    name: item?.name || state.results[0]?.name || 'Ảnh từ Thư viện',
    sourceId: state.viewId || '',
  });
  if (!accepted) return;
  if (item) {
    $('#prompt').value = item.prompt || $('#prompt').value;
    $('#negative').value = withWatermarkGuard(item.negative || $('#negative').value);
  }
  setGenerationMode('img2img');
  closeSheet($('#sheetImage'));
  showTab('create');
  $('#img2imgSourceCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('Đã chọn ảnh gốc; chỉnh denoise rồi bấm Tạo từ ảnh');
}

async function upscaleCurrentImage() {
  if (state.busy) {
    toast('Đang có job chạy; chờ hoàn tất trước khi upscale.', { error: true });
    return;
  }
  const sourceId = state.viewId;
  const sourceUrl = $('#imageView').src;
  if (!sourceUrl) return;
  const scale = Number($('#upscaleScale').value);
  const upscaler = $('#upscaleName').value;
  if (![1.5, 2, 3, 4].includes(scale) || !upscaler) {
    $('#upscaleStatus').textContent = 'Tỉ lệ hoặc upscaler không hợp lệ.';
    return;
  }
  const width = Number($('#imageView').naturalWidth) || 0;
  const height = Number($('#imageView').naturalHeight) || 0;
  if (width && height && (width * scale > 4096 || height * scale > 4096)) {
    $('#upscaleStatus').textContent = 'Kích thước đầu ra vượt 4096×4096; giảm tỉ lệ để tránh hết RAM/VRAM.';
    toast('Ảnh upscale quá lớn; hãy giảm tỉ lệ.', { error: true, ms: 5000 });
    return;
  }

  const source = sourceId ? await store.getImage(sourceId) : null;
  state.busy = true;
  state.controller = new AbortController();
  $('#imageUpscaleBtn').disabled = true;
  $('#upscaleCancelBtn').classList.remove('hidden');
  $('#upscaleStatus').textContent = '⏳ Đang chuẩn bị ảnh và gửi job upscale…';
  try {
    const blob = source?.blob || await (await fetch(sourceUrl)).blob();
    if (blob.size > 20 * 1024 * 1024) throw new Error('Ảnh đầu vào vượt 20 MiB.');
    const encoded = await blobToBase64(blob);
    const api = client();
    state.activeClient = api;
    const result = await api.extras({
      image: encoded,
      resize_mode: 0,
      show_extras_results: true,
      gfpgan_visibility: 0,
      codeformer_visibility: 0,
      codeformer_weight: 0,
      upscaling_resize: scale,
      upscaler_1: upscaler,
      upscaler_2: 'None',
      extras_upscaler_2_visibility: 0,
      upscale_first: false,
    }, {
      signal: state.controller.signal,
      onJob: (job) => { state.activeJobId = job.job_id; },
      onProgress: (info) => {
        const percent = Math.round((Number(info.progress) || 0) * 100);
        $('#upscaleStatus').textContent = `⏳ Job ${state.activeJobId.slice(0, 8)} · ${percent}% · không tạo lại ảnh bằng prompt`;
      },
      onDownload: ({ loaded, total }) => {
        $('#upscaleStatus').textContent = `⬇️ Đang tải bản upscale: ${formatBytes(loaded)}/${formatBytes(total)}`;
      },
    });
    const output = result.images[0];
    const extension = ({ 'image/jpeg': 'jpg', 'image/webp': 'webp' })[output.type] || 'png';
    const info = { ...(result.info || {}), operation: 'extras', scale, upscaler, source_id: sourceId || '' };
    const saved = await store.addImage({
      blob: output,
      name: `anime3-upscale-${Date.now()}.${extension}`,
      mime: output.type || 'image/png',
      thumb: await makeThumb({ blob: output }),
      prompt: source?.prompt || '',
      negative: source?.negative || '',
      seed: source?.seed ?? null,
      info,
      params: { operation: 'extras', scale, upscaler },
      index: 0,
    });
    if (state.viewUrl) URL.revokeObjectURL(state.viewUrl);
    state.viewUrl = URL.createObjectURL(output);
    openImage(saved.id, state.viewUrl, `Upscale ${scale}× · ${upscaler} · ảnh gốc được giữ nguyên`);
    $('#upscaleStatus').textContent = `✅ Đã lưu bản upscale vào Thư viện · job ${result.jobId.slice(0, 8)}`;
    toast('Đã upscale và lưu ảnh mới vào Thư viện');
    renderGallery();
  } catch (error) {
    const message = error?.name === 'AbortError'
      ? '⛔ Đã huỷ job upscale.'
      : (error instanceof ForgeError ? error.message : `Lỗi upscale: ${error.message}`);
    $('#upscaleStatus').textContent = message;
    if (error?.name !== 'AbortError') toast(message, { error: true, ms: 6000 });
  } finally {
    state.busy = false;
    state.controller = null;
    state.activeClient = null;
    state.activeJobId = '';
    $('#imageUpscaleBtn').disabled = false;
    $('#upscaleCancelBtn').classList.add('hidden');
  }
}

async function cancelUpscale() {
  if (!state.busy) return;
  $('#upscaleStatus').textContent = '⛔ Đang huỷ job upscale…';
  if (state.activeClient && state.activeJobId) {
    await state.activeClient.cancelJob(state.activeJobId);
  } else {
    await client().interrupt();
  }
  state.controller?.abort();
}

async function imageFile(image) {
  const blob = image?.blob || await (await fetch(image?.dataUrl || image)).blob();
  return new File([blob], image?.name || `anime3-${Date.now()}.png`, {
    type: blob.type || 'image/png',
  });
}

async function blobToBase64(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  // Chia nhỏ để không vượt giới hạn số argument của fromCharCode trên WebView.
  for (let offset = 0; offset < bytes.length; offset += 32768) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  }
  return btoa(binary);
}

/** Lưu thật bằng MediaStore trong APK; trên web dùng download của trình duyệt. */
async function saveImageToDevice(image) {
  if (!image) return;
  try {
    const file = await imageFile(image);
    const plugin = window.Capacitor?.Plugins?.Anime3Media;
    const isNative = window.Capacitor?.isNativePlatform?.();
    if (isNative && !plugin?.saveImage) {
      throw new Error('APK chưa nạp được plugin lưu ảnh. Hãy cài bản APK mới rồi đóng/mở lại app.');
    }
    if (isNative) {
      const saved = await plugin.saveImage({
        data: await blobToBase64(file), name: file.name, mime: file.type,
      });
      $('#imageSaveLocation').textContent = `Đã lưu thành công: ${saved.path}`;
      toast(`Đã lưu: ${saved.path}`, { ms: 7000 });
      return saved;
    }
    const url = URL.createObjectURL(file);
    const link = h('a', { href: url, download: file.name });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    $('#imageSaveLocation').textContent = 'Trình duyệt đã nhận lệnh tải; kiểm tra thông báo tải xuống hoặc thư mục Download.';
    toast('Đã gửi lệnh tải — mở thông báo trình duyệt hoặc thư mục Download để xem nơi lưu.',
      { ms: 6000 });
    return { path: 'Download (tuỳ cài đặt trình duyệt)' };
  } catch (error) {
    toast(`Không lưu được ảnh: ${error.message}`, { error: true, ms: 6000 });
    return null;
  }
}

async function shareImage(image) {
  if (!image) return;
  try {
    const file = await imageFile(image);
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: 'Anime3' });
      return;
    }
    // WebView không có share sheet/download Blob đáng tin cậy: dùng MediaStore của APK.
    await saveImageToDevice(image);
  } catch (error) {
    toast(`Không chia sẻ được: ${error.message}`, { error: true });
  }
}

// ------------------------------------------------------------------ kết nối
function setConn(text, variant = '') {
  const node = $('#connBtn');
  node.textContent = variant === 'ok' ? `● ${text}` : text;
  node.className = `conn ${variant}`;
}

let pingTimer = null;
/** Ping Forge; trả về `true` nếu kết nối được. Cập nhật luôn thanh trên + tab Máy chủ. */
async function pingServer() {
  clearTimeout(pingTimer);
  setConn('đang kiểm tra…');
  try {
    const info = await client().ping();
    const model = info.model
      ? info.model.split(/[\\/]/).pop().replace(/\.safetensors$/, '')
      : '';
    state.connected = true;
    state.connectedModel = model;
    setConn(model ? `● ${model}` : '● đã kết nối', 'ok');
    $('#connInfo').textContent = model
      ? `Đã kết nối Forge · model: ${model}`
      : 'Đã kết nối Forge.';
    if (state.settings.apiUrl) {
      store.rememberLink(state.settings, state.settings.apiUrl, { ok: true, model });
      store.saveSettings(state.settings);
    }
    renderServerTab();
    return true;
  } catch (error) {
    state.connected = false;
    state.connectedModel = '';
    setConn('chưa kết nối', 'bad');
    $('#connInfo').textContent = error.message || 'Không kết nối được.';
    if (state.settings.apiUrl) {
      store.rememberLink(state.settings, state.settings.apiUrl, { ok: false });
      store.saveSettings(state.settings);
    }
    renderServerTab();
    return false;
  } finally {
    // kiểm tra lại mỗi 60 giây để link tunnel hết hạn là biết ngay
    pingTimer = setTimeout(pingServer, 60000);
  }
}

// ------------------------------------------------------------------ tab Máy chủ (Colab)
function colabInfo() {
  return state.data?.raw?.colab || FALLBACK_COLAB;
}

function shortUrl(url) {
  return String(url || '').replace(/^https?:\/\//, '').slice(0, 42);
}

function setServerPill(text, variant = '') {
  const pill = $('#serverState');
  if (!pill) return;
  pill.textContent = text;
  pill.className = `pill ${variant}`;
}

/** Vẽ lại toàn bộ tab Máy chủ từ state (không gọi mạng). */
function renderServerTab() {
  if (!$('#serverState')) return;
  if (state.busy) setServerPill('đang sinh ảnh…', 'busy');
  else if (state.connected) setServerPill('đã kết nối', 'ok');
  else if (state.settings.apiUrl) setServerPill('không kết nối được', 'bad');
  else setServerPill('chưa có địa chỉ', '');

  const where = state.settings.apiUrl || 'cùng origin với app';
  $('#serverModel').textContent = state.connected
    ? `Model: ${state.connectedModel || '(không rõ)'} · ${where}`
    : state.settings.apiUrl
      ? `Đã lưu ${state.settings.apiUrl} nhưng chưa phản hồi — link gradio.live hết hạn sau vài giờ.`
      : 'Chưa có địa chỉ Forge. Bấm “Mở Colab & chạy” để bắt đầu.';

  const input = $('#serverUrl');
  if (document.activeElement !== input) input.value = state.settings.apiUrl || '';
  $('#autoConnect').checked = state.settings.autoConnect !== false;

  const colab = colabInfo();
  $('#serverHelp').textContent = state.data
    ? `Notebook: ${colab.repo} · bản ${colab.branch} · ${colab.notebook}`
    : 'Chưa nạp được dữ liệu app — vẫn dùng được ô địa chỉ Forge bên trên.';

  renderLinks();
}

function renderLinks() {
  const box = $('#linkList');
  const list = state.settings.links || [];
  $('#linkEmpty').classList.toggle('hidden', list.length > 0);
  box.replaceChildren(...list.map((item) => {
    const status = item.ok === true ? '✅' : item.ok === false ? '❌' : '•';
    const when = item.at ? new Date(item.at).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '';
    return h('button', {
      class: `tag-row${item.url === state.settings.apiUrl ? ' selected' : ''}`,
      type: 'button',
      onclick: () => connectTo(item.url),
    },
    h('span', { class: 'tag-main' },
      h('span', { class: 'tag-en' }, `${status} ${shortUrl(item.url)}`),
      h('span', { class: 'tag-vi' }, [item.model || 'Forge', when].filter(Boolean).join(' · ')),
    ),
    h('span', { class: 'tag-count' }, item.ok === true ? 'sống' : item.ok === false ? 'chết' : 'chưa thử'));
  }));
}

/** Mở Colab bằng một nút: Custom Tab (APK) hoặc tab mới của trình duyệt (PWA). */
async function openColab() {
  const url = colabInfo().url;
  const plugin = window.Capacitor?.Plugins?.Browser;
  if (plugin?.open) {
    try {
      await plugin.open({ url });
      toast('Đã mở Colab — chạy Run all rồi quay lại app');
      return;
    } catch (error) {
      console.warn('Không mở được Custom Tab', error);
    }
  }
  const opened = window.open(url, '_blank', 'noopener');
  if (!opened && !plugin) {
    toast(`Trình duyệt chặn tab mới. Mở tay: ${url}`, { error: true, ms: 6000 });
    $('#serverUrl').value = url;
    return;
  }
  toast('Đã mở Colab — chạy Run all rồi quay lại app');
}

/**
 * Kết nối một link Forge: lưu vào lịch sử, ping thử, cập nhật UI.
 * Trả về `true` nếu Forge trả lời.
 */
async function connectTo(rawUrl, { silent = false } = {}) {
  const url = core.normalizeBaseUrl(rawUrl);
  if (!url) {
    toast('Dán link Forge, ví dụ https://abc123.gradio.live', { error: true });
    return false;
  }
  if (!/^https?:\/\/[^\s]+$/i.test(url)) {
    toast('Link không hợp lệ', { error: true });
    return false;
  }
  state.settings.apiUrl = url;
  $('#apiUrl').value = url;
  $('#serverUrl').value = url;
  store.rememberLink(state.settings, url);
  saveSettingsNow();
  renderServerTab();
  if (!silent) toast(`Đang kết nối ${shortUrl(url)}…`);
  const ok = await pingServer();
  if (ok) toast('Đã kết nối Forge');
  return ok;
}

async function readClipboard() {
  try {
    if (navigator.clipboard?.readText) return await navigator.clipboard.readText();
  } catch (error) {
    // Chrome/WebView có thể từ chối đọc clipboard không có thao tác người dùng
  }
  return '';
}

async function pasteAndConnect() {
  const text = await readClipboard();
  if (!text) {
    toast('Không đọc được clipboard — dán tay vào ô bên dưới', { error: true });
    $('#serverUrl').focus();
    return;
  }
  const url = core.extractForgeUrl(text);
  if (!url) {
    toast('Clipboard không có link Forge (gradio.live / trycloudflare)', { error: true });
    return;
  }
  await connectTo(url);
}

async function copyText(text, label) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      toast(`Đã copy ${label} — dán vào ô của Colab`);
      return;
    }
  } catch (error) {
    // rơi xuống dưới
  }
  $('#serverHelp').textContent = `${label}: ${text}`;
  toast('Không copy tự động được — lệnh đã hiện dưới ô địa chỉ', { ms: 4000 });
}

/**
 * Tự nhận link khi quay lại app: người dùng copy link trong Colab (hoặc nút copy
 * của Colab), chuyển sang app → đọc clipboard → thấy link Forge → kết nối luôn.
 * Đây là phần "chạy Colab ngay trong app" khả thi nhất: Google không cho nhúng
 * Colab vào WebView (chặn đăng nhập) và không có API bấm Run all hộ.
 */
let lastClipboardUrl = '';
function setupResumeWatch() {
  const check = () => setTimeout(checkClipboardForLink, 700);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check();
  });
  window.addEventListener('focus', check);
}

async function checkClipboardForLink() {
  if (state.settings.autoConnect === false) return;
  if (state.connected || state.busy) return;
  if (!navigator.clipboard?.readText) return;
  const text = await readClipboard();
  const url = core.extractForgeUrl(text);
  if (!url || url === state.settings.apiUrl || url === lastClipboardUrl) return;
  lastClipboardUrl = url;
  toast(`Tự nhận link trong clipboard: ${shortUrl(url)}`, { ms: 3000 });
  await connectTo(url, { silent: true });
}

async function runDiagnose() {
  if (state.diagnoseBusy) return;
  state.diagnoseBusy = true;
  const button = $('#diagnoseBtn');
  const out = $('#diagnoseOut');
  button.disabled = true;
  button.textContent = 'Đang kiểm tra…';
  out.setAttribute('aria-busy', 'true');
  out.replaceChildren(h('div', { class: 'diag-loading' },
    h('span', { class: 'diag-spinner', 'aria-hidden': 'true' }),
    h('span', { text: 'Đang kiểm tra 6 endpoint, vui lòng chờ…' }),
  ));
  try {
    const result = await client().diagnose();
    const healthy = result.hasApi && result.hasProgress;
    const summary = !result.anyOk
      ? 'Không kết nối được máy chủ'
      : !result.hasApi
        ? 'Máy chủ phản hồi nhưng thiếu API'
        : !result.hasProgress
          ? 'API hoạt động, chưa đọc được tiến trình'
          : 'Kết nối ổn, sẵn sàng tạo ảnh';
    const summaryVariant = healthy ? 'ok' : result.anyOk ? 'warn' : 'bad';

    const lines = result.checks.map((item) => {
      const optionalFailure = !item.ok && item.optional;
      const variant = item.ok ? 'ok' : optionalFailure ? 'warn' : 'bad';
      const status = item.ok ? 'OK' : item.status ? `HTTP ${item.status}` : 'Lỗi mạng';
      const detail = optionalFailure
        ? `${item.detail} Endpoint dự phòng này không bắt buộc.`
        : item.detail;
      return h('div', { class: `diag-line ${variant}` },
        h('span', { class: 'diag-icon', 'aria-hidden': 'true', text: item.ok ? '✓' : '!' }),
        h('div', { class: 'diag-copy' },
          h('div', { class: 'diag-title' },
            h('strong', { text: item.label }),
            h('span', { class: `diag-status ${variant}`, text: status }),
          ),
          h('code', { class: 'path', text: `${item.method} /${item.path}` }),
          h('span', { class: 'diag-detail', text: detail }),
        ),
      );
    });

    const hints = [];
    if (!result.anyOk) {
      hints.push('Kiểm tra link tunnel còn sống và đúng địa chỉ Forge. Lấy link mới bằng lệnh ở trên, rồi kết nối lại.');
    } else if (!result.hasApi) {
      hints.push('Forge cần chạy với cờ --api để app có thể gửi yêu cầu tạo ảnh. Bộ cài của Anime3 đã bật sẵn cờ này.');
    }
    if (result.anyOk && !result.hasProgress) {
      hints.push('Vẫn có thể tạo ảnh, nhưng thanh tiến trình sẽ không cập nhật. Hãy cập nhật Forge hoặc kiểm tra cờ --api.');
    }
    if (result.hasApi && !result.hasAsyncJobs) {
      hints.push('Colab chưa có job nền + file stream. Chạy lại notebook một ô để cập nhật extension; app không quay lại API base64 cũ.');
    }
    const hasNetworkError = result.checks.some((item) => !item.ok && item.status === 0);
    if (hasNetworkError && location.protocol === 'https:' && location.hostname === 'localhost') {
      hints.push('Nếu chỉ APK gặp lỗi mạng còn trình duyệt dùng được, hãy bật --cors-allow-origins cho Forge.');
    }
    out.replaceChildren(
      h('div', { class: `diag-summary ${summaryVariant}` },
        h('span', { class: 'diag-summary-icon', 'aria-hidden': 'true', text: healthy ? '✓' : '!' }),
        h('div', {},
          h('strong', { text: summary }),
          h('span', { text: result.base }),
        ),
      ),
      h('div', { class: 'diag-list' }, ...lines),
      ...(hints.length ? [h('div', { class: 'diag-advice' },
        h('strong', { text: 'Cách xử lý' }),
        ...hints.map((hint) => h('p', { text: hint })),
      )] : []),
    );
  } catch (error) {
    out.replaceChildren(h('div', { class: 'diag-summary bad' },
      h('span', { class: 'diag-summary-icon', 'aria-hidden': 'true', text: '!' }),
      h('div', {},
        h('strong', { text: 'Không chẩn đoán được' }),
        h('span', { text: error.message }),
      ),
    ));
  } finally {
    state.diagnoseBusy = false;
    button.disabled = false;
    button.textContent = '🩺 Chẩn đoán lại';
    out.removeAttribute('aria-busy');
  }
}

async function testConnection() {
  $('#connInfo').textContent = 'Đang kiểm tra…';
  try {
    const api = client();
    const info = await api.ping();
    const model = info.model || '(không rõ)';
    $('#connInfo').textContent = `✅ Kết nối được: ${model}`;
    setConn(`● ${String(model).split(/[\\/]/).pop()}`, 'ok');
  } catch (error) {
    $('#connInfo').textContent = `❌ ${error.message}`;
    setConn('chưa kết nối', 'bad');
  }
}

async function installApp() {
  if (!state.installEvent) {
    toast('Trình duyệt không hỗ trợ cài trực tiếp — dùng menu "Thêm vào màn hình chính".');
    return;
  }
  state.installEvent.prompt();
  const choice = await state.installEvent.userChoice.catch(() => null);
  state.installEvent = null;
  $('#installBtn').classList.add('hidden');
  if (choice?.outcome === 'accepted') toast('Đã cài app ra màn hình chính');
}

// ------------------------------------------------------------------ khởi động
init();
