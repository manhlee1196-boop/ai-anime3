"""Panel Gradio dùng chung: bảng/thumbnail phân trang, chọn ảnh gốc và dùng seed.

State chỉ có số trang, tối đa 24 id SQLite và id/signature ảnh đã chọn; không chứa PIL/base64.
"""
import html
import sqlite3

import gradio as gr


class HistoryPanel:
    def __init__(self, get_store, seed_component):
        self.get_store = get_store
        gr.Markdown(
            "Ảnh đã lưu từ **txt2img / img2img / Prompt VN** trong runtime. "
            "Bấm **Làm mới** để đọc ảnh cũ; thumbnail nhẹ, chọn một ảnh để xem/tải bản gốc. "
            "Chỉ mục nằm trên đĩa, không giữ toàn bộ ảnh trong RAM. "
            "Người có link UI cũng có thể xem album này."
        )
        with gr.Row(elem_classes=["wai-row-2"]):
            self.refresh_button = gr.Button("🔄 Làm mới ảnh đã tạo", variant="primary")
            self.previous_button = gr.Button("← Trang trước")
            self.next_button = gr.Button("Trang sau →")
            self.page_size = gr.Dropdown([12, 24], value=12, label="Ảnh mỗi trang", allow_custom_value=False)
        self.note = gr.Markdown("Chưa đọc lịch sử. Bấm **Làm mới**; không sinh thêm ảnh.")
        self.gallery = gr.Gallery(label="Ảnh đã tạo — chọn thumbnail", columns=4, height=300,
                                  object_fit="contain", allow_preview=False, show_download_button=False,
                                  elem_classes=["wai-gallery", "wai-history-gallery"])
        self.table = gr.Dataframe(headers=["Thời gian lưu (UTC+7)", "Tên ảnh", "Seed", "Kích thước", "Dung lượng"],
                                  datatype="str", type="array", interactive=False, height=220, wrap=True,
                                  elem_classes=["wai-history-table"],
                                  label="Bảng ảnh đã tạo — chọn một dòng")
        self.ids = gr.State([])
        self.page_number = gr.State(1)
        self.selected_id = gr.State(None)
        with gr.Row(elem_classes=["wai-row-2"]):
            self.original = gr.Image(label="Ảnh gốc đã chọn", type="filepath", format="png",
                                     interactive=False, height=420, elem_classes=["wai-history-original"])
            with gr.Column():
                self.download = gr.File(label="Tải ảnh gốc (giữ metadata)", interactive=False)
                self.selected_note = gr.Markdown("Chưa chọn ảnh trong lịch sử.")
                self.seed_button = gr.Button("🔒 Dùng seed ảnh lịch sử")
        self.page_outputs = [self.gallery, self.table, self.ids, self.page_number, self.note,
                             self.selected_id, self.original, self.download, self.selected_note]
        self.refresh_button.click(self.refresh, [self.page_size], self.page_outputs,
                                  concurrency_limit=1, concurrency_id="wai_history")
        self.previous_button.click(self.previous, [self.page_number, self.page_size], self.page_outputs,
                                   concurrency_limit=1, concurrency_id="wai_history")
        self.next_button.click(self.next, [self.page_number, self.page_size], self.page_outputs,
                               concurrency_limit=1, concurrency_id="wai_history")
        self.page_size.change(self.first_page, [self.page_size], self.page_outputs,
                              concurrency_limit=1, concurrency_id="wai_history")
        self.gallery.select(self.select, [self.ids], [self.selected_id, self.original, self.download, self.selected_note],
                            concurrency_limit=1, concurrency_id="wai_history")
        self.table.select(self.select, [self.ids], [self.selected_id, self.original, self.download, self.selected_note],
                          concurrency_limit=1, concurrency_id="wai_history")
        self.seed_button.click(self.use_seed, [self.selected_id], [seed_component, self.selected_note], queue=False)

    @staticmethod
    def _size(value):
        try:
            return 24 if int(value) == 24 else 12
        except (TypeError, ValueError, OverflowError):
            return 12

    @staticmethod
    def _unavailable():
        return [], [], [], 1, "Chưa đọc được thư mục/chỉ mục ảnh; ảnh gốc vẫn được giữ nguyên.", None, None, None, ""

    def _page(self, number, size):
        try:
            return self._read_page(number, size)
        except (OSError, ValueError, sqlite3.Error):
            return self._unavailable()

    def _read_page(self, number, size):
        store = self.get_store()
        records, total, number, pages = store.page(number, self._size(size))
        gallery, rows, ids = [], [], []
        for record in records:
            thumbnail = store.thumbnail(record)
            if thumbnail is None:
                continue
            caption = html.escape(record.table_row()[1])
            gallery.append((thumbnail, caption))
            rows.append(record.table_row())
            ids.append(record.id)
        note = f"**{total} ảnh đã lưu · Trang {number}/{pages} · Hiện {len(ids)} ảnh.**"
        if total == 0:
            note += " Chưa có ảnh trong các thư mục output; bấm Làm mới sau khi sinh/lưu ảnh."
        if store.scan_limited:
            note += " Lượt quét có giới hạn hoặc thư mục chưa đọc được; chỉ mục có thể chưa đầy đủ."
        return gallery, rows, ids, number, note, None, None, None, "Chọn một thumbnail hoặc một dòng để xem ảnh gốc."

    def refresh(self, size=12):
        try:
            self.get_store().refresh()
            return self._page(1, size)
        except (OSError, ValueError, sqlite3.Error):
            return self._unavailable()

    def first_page(self, size=12):
        return self._page(1, size)

    def previous(self, number, size=12):
        return self._page(max(1, int(number or 1) - 1), size)

    def next(self, number, size=12):
        return self._page(int(number or 1) + 1, size)

    def select(self, ids, evt: gr.SelectData):
        index = evt.index
        index = index[0] if isinstance(index, (list, tuple)) and index else index
        if type(index) is not int or not isinstance(ids, list) or not 0 <= index < len(ids):
            return None, None, None, "Chọn một ảnh trong trang lịch sử hiện tại."
        try:
            record = self.get_store().get(ids[index])
        except (OSError, ValueError, sqlite3.Error):
            record = None
        if record is None:
            return None, None, None, "Ảnh đã đổi/không còn trên đĩa. Bấm Làm mới lịch sử."
        seed_note = "Ảnh lưới: không dùng seed để tái tạo một ảnh đơn." if record.is_grid else (
            f"Seed **{record.seed}**." if record.seed is not None else "Ảnh không có seed xác định trong metadata.")
        token = {"id": record.id, "mtime_ns": record.mtime_ns, "size": record.size}
        return token, record.path, record.path, f"**{record.width}×{record.height}** · {seed_note} Bản gốc không bị nén/sửa."

    def use_seed(self, selection):
        try:
            record = self.get_store().get(selection.get("id")) if isinstance(selection, dict) else None
        except (OSError, ValueError, sqlite3.Error):
            record = None
        if record is None or record.seed is None or record.is_grid or (
                record.mtime_ns, record.size) != (selection.get("mtime_ns"), selection.get("size")):
            return gr.skip(), "Chọn một ảnh đơn có seed trong lịch sử trước."
        return record.seed, f"🔒 Đã điền seed {record.seed}. Chỉ đổi seed; prompt và sampling không tự thay theo ảnh cũ."

    def after_generation(self, event):
        """Sau callback đã postprocess kết quả, đọc file vừa lưu; không nối PIL vào State."""
        event.success(self.refresh, [self.page_size], self.page_outputs,
                      concurrency_limit=1, concurrency_id="wai_history")
