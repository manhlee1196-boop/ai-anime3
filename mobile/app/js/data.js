/**
 * Nạp dữ liệu tag (`data/tags.json` hoặc bản nén `tags.json.gz`) và tra cứu.
 *
 * Dữ liệu do `python3 mobile/build_data.py` sinh ra từ chính các CSV của repo:
 * 95.939 tag phổ biến + mọi tag có bản dịch tiếng Việt, kèm 506 tag phong cách.
 */

import { normKey, OTHER_GROUP } from './core.js';

const DATA_GZ = 'data/tags.json.gz';
const DATA_JSON = 'data/tags.json';

/** Đọc JSON, ưu tiên bản .gz nếu trình duyệt/WebView giải nén được. */
async function fetchData(fetchImpl = fetch) {
  if (typeof DecompressionStream === 'function') {
    try {
      const response = await fetchImpl(DATA_GZ, { cache: 'force-cache' });
      if (response.ok && response.body) {
        const stream = response.body.pipeThrough(new DecompressionStream('gzip'));
        return JSON.parse(await new Response(stream).text());
      }
    } catch (error) {
      // rơi xuống bản .json — vẫn chạy, chỉ chậm hơn lần đầu
      console.warn('Không dùng được tags.json.gz, thử tags.json', error);
    }
  }
  const response = await fetchImpl(DATA_JSON, { cache: 'force-cache' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} khi tải ${DATA_JSON}`);
  }
  return JSON.parse(await response.text());
}

/**
 * Mục lục tra cứu của app.
 *
 * Mỗi tag được giữ dưới dạng mảng `[tag, count, category, groupIndex, vi|0]` để
 * 96.000 tag vẫn vừa bộ nhớ điện thoại; khoá tìm kiếm (bỏ dấu, bỏ `_`) tính một
 * lần lúc nạp — gõ tới đâu chỉ còn so chuỗi.
 */
export class TagData {
  constructor(payload) {
    this.raw = payload;
    this.rows = payload.tags || [];
    this.groups = payload.groups || [];
    this.groupLabels = payload.group_labels || [];
    this.browseGroups = payload.browse_groups || [];
    this.categories = payload.categories || {};
    this.presets = payload.presets || {};
    this.styles = payload.styles || [];
    this.quick = payload.quick || {};
    this._build();
  }

  _build() {
    const size = this.rows.length;
    this.en = new Array(size);
    this.vi = new Array(size);
    this.exact = new Map();
    for (let i = 0; i < size; i += 1) {
      const row = this.rows[i];
      const en = normKey(row[0]);
      this.en[i] = en;
      this.vi[i] = row[4] ? normKey(row[4]) : '';
      if (!this.exact.has(en)) this.exact.set(en, i);
    }
    this.styleIndex = this.styles.map((row) => ({
      tag: row[0],
      vi: row[1],
      group: row[2],
      key: normKey(row[0]),
      viKey: normKey(row[1]),
    }));
  }

  /** Tag (đã chuẩn) -> nhóm để xếp prompt; không biết thì trả về nhóm "other". */
  groupIndexOf(tag) {
    const key = normKey(tag);
    if (!key) return OTHER_GROUP;
    const index = this.exact.get(key);
    if (index === undefined) return OTHER_GROUP;
    return this.rows[index][3] ?? OTHER_GROUP;
  }

  /** Nghĩa tiếng Việt của tag (nếu có). */
  viOf(tag) {
    const index = this.exact.get(normKey(tag));
    return index === undefined ? '' : (this.rows[index][4] || '');
  }

  /** Số bài đăng của tag, để hiện "độ mạnh". */
  countOf(tag) {
    const index = this.exact.get(normKey(tag));
    return index === undefined ? 0 : this.rows[index][1];
  }

  /**
   * Tìm tag: khớp tiếng Anh trước (chính xác > đầu từ > chứa), rồi tiếng Việt.
   * Cùng mức thì tag phổ biến hơn đứng trước.
   */
  search(query, { limit = 40, category = null, group = null } = {}) {
    const q = normKey(query);
    // UI giữ nhóm theo key (`appearance`), còn từng dòng lưu index (8).
    // Quy đổi tại một điểm để cả số lẫn chuỗi đều lọc đúng, không trả danh sách rỗng.
    const groupIndex = this.resolveGroup(group);
    if (groupIndex === -1) return [];
    if (!q) {
      return this._popular({ limit, category, group: groupIndex });
    }
    const hits = [];
    const words = q.split(' ');
    for (let i = 0; i < this.rows.length; i += 1) {
      const row = this.rows[i];
      if (category !== null && row[2] !== category) continue;
      if (groupIndex !== null && row[3] !== groupIndex) continue;
      const en = this.en[i];
      const vi = this.vi[i];
      let score = -1;
      if (en === q) score = 0;
      else if (en.startsWith(q)) score = 10;
      else if (en.includes(` ${q}`)) score = 20;
      else if (en.includes(q)) score = 30;
      else if (vi && vi === q) score = 5;
      else if (vi && vi.startsWith(q)) score = 15;
      else if (vi && vi.includes(q)) score = 25;
      else if (words.length > 1 && words.every((w) => en.includes(w))) score = 40;
      if (score < 0) continue;
      hits.push({ index: i, score, count: row[1] });
    }
    hits.sort((a, b) => (a.score - b.score) || (b.count - a.count));
    return hits.slice(0, limit).map((hit) => this.describe(hit.index));
  }

  /** Nhận cả index nhóm lẫn key; nhóm không tồn tại trả -1 để không lọc sai thành "tất cả". */
  resolveGroup(group) {
    if (group === null || group === undefined || group === '' || group === 'all') return null;
    if (Number.isInteger(group)) return group >= 0 && group < this.groups.length ? group : -1;
    return this.groups.indexOf(String(group));
  }

  _popular({ limit = 40, category = null, group = null } = {}) {
    const out = [];
    for (let i = 0; i < this.rows.length && out.length < limit; i += 1) {
      const row = this.rows[i];
      if (category !== null && row[2] !== category) continue;
      if (group !== null && row[3] !== group) continue;
      out.push(this.describe(i));
    }
    return out;
  }

  /** Mảng dữ liệu -> object dễ đọc cho UI. */
  describe(index) {
    const row = this.rows[index];
    return {
      tag: row[0],
      count: row[1],
      category: row[2],
      categoryLabel: this.categories[String(row[2])] || 'Khác',
      group: row[3],
      groupKey: this.groups[row[3]] || 'other',
      groupLabel: this.groupLabels[row[3]] || 'Khác',
      vi: row[4] || '',
    };
  }

  /** Tìm trong 506 tag phong cách vẽ. */
  searchStyles(query, { limit = 60, group = null } = {}) {
    const q = normKey(query);
    const out = [];
    for (const item of this.styleIndex) {
      if (group && item.group !== group) continue;
      let score;
      if (!q) score = 0;
      else if (item.key.startsWith(q)) score = 1;
      else if (item.key.includes(q)) score = 2;
      else if (item.viKey.startsWith(q)) score = 3;
      else if (item.viKey.includes(q)) score = 4;
      else continue;
      out.push({ ...item, score });
    }
    out.sort((a, b) => (a.score - b.score) || a.tag.localeCompare(b.tag));
    return out.slice(0, limit);
  }

  /** Nhóm phong cách theo thứ tự xuất hiện trong CSV. */
  styleGroups() {
    const seen = [];
    for (const item of this.styleIndex) {
      if (!seen.includes(item.group)) seen.push(item.group);
    }
    return seen;
  }

  /** Nhãn ngắn có dấu cho số bài đăng: 1.2M / 345k. */
  static formatCount(count) {
    const value = Number(count) || 0;
    if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3) return `${Math.round(value / 1e3)}k`;
    return String(value);
  }
}

/** Tải dữ liệu; ném lỗi có thông điệp tiếng Việt nếu thiếu file. */
export async function loadTagData(fetchImpl = fetch) {
  let payload;
  try {
    payload = await fetchData(fetchImpl);
  } catch (error) {
    throw new Error(
      `Không tải được dữ liệu tag (${error.message}). Chạy "python3 mobile/build_data.py" `
      + 'ở thư mục repo để sinh mobile/app/data/tags.json, rồi tải lại trang.',
    );
  }
  if (!Array.isArray(payload?.tags) || !payload.tags.length) {
    throw new Error('Dữ liệu tag rỗng — sinh lại bằng "python3 mobile/build_data.py".');
  }
  return new TagData(payload);
}
