# Prompt dài mà không rơi chi tiết — WAI-Illustrious v17 (SDXL)

Tài liệu này trả lời đúng một câu: **làm sao để model hiểu prompt dài mà không bỏ chi tiết?**
Câu trả lời ngắn: *không viết dài hơn — hãy giữ prompt trong ngân sách token, xếp chi tiết
quan trọng lên đầu, và chia phần còn lại sang lượt sau.*

Mọi con số token dưới đây đo bằng `colab/prompt_lib/limits.py` (ước lượng ±10%, không kèm
tokenizer CLIP). Đo prompt của bạn: mục **📏 Prompt dài** trong app, hoặc

```bash
python3 -c "import sys; sys.path.insert(0,'colab'); \
from prompt_lib.limits import audit_prompt; \
print(audit_prompt(open('prompt.txt').read())['advice'])"
```

---

## 1. Vì sao chi tiết bị "rơi"

| Sự thật | Hệ quả cho prompt |
|---|---|
| CLIP đọc **75 token** mỗi cửa sổ (77 gồm BOS/EOS) | Prompt 200 token bị cắt thành 3 cửa sổ, model không "thấy" đều nhau |
| SDXL có **2 text encoder** (CLIP-L 768 + OpenCLIP-bigG 1280), mỗi bên 77 token | Câu chữ phải ngắn mới "ăn" cả hai; Illustrious càng nhạy với tag hơn câu dài |
| Forge nối các cửa sổ thành chuỗi cho cross-attention | Token **càng xa đầu prompt càng ít trọng số**; cửa sổ 1 quyết định bố cục, cửa sổ 3 chỉ còn gợi ý |
| `(tag:1.2)` chiếm thêm token (ngoặc + số) | Nhiều trọng số = prompt dài thêm mà không thêm chi tiết |

**Ngân sách thực dụng** (đo bằng công cụ trong app):

| Độ dài | Trạng thái | Nên làm |
|---|---|---|
| ≤ 75 token (≈ 12–20 tag) | 🟢 chắc | mọi tag đều nằm trong cửa sổ đầu — model đọc đủ |
| 76–150 token (≈ 20–40 tag) | 🟡 còn tốt | chi tiết bắt buộc lên đầu; tag trang trí xuống cuối |
| 151–225 token | 🔴 loãng | cửa sổ 3 gần như vô tác dụng — cắt hoặc chia 2 lượt |
| > 225 token | ⛔ | model chỉ còn đọc khoảng 1/3 đầu; phần sau là "trang trí" |

---

## 2. Ví dụ cùng một cảnh: 188 token → 85 token mà **không mất chi tiết**

**Trước (58 tag, 188 token, 3 cửa sổ, 9 tag rơi sang vùng loãng):**

```
masterpiece, best quality, very aesthetic, absurdres, newest, highres, 1girl, solo,
female, girl, young woman, blue eyes, blue_eyes, eyes, detailed eyes, long hair,
long_hair, hair, silver hair, silver_hair, straight hair, school uniform,
school_uniform, sailor collar, sailor_collar, serafuku, red ribbon, red_ribbon,
pleated skirt, pleated_skirt, miniskirt, kneehighs, black legwear, black_legwear,
loafers, school shoes, smile, open mouth, open_mouth, blush, looking at viewer,
looking_at_viewer, standing, hand up, waving, classroom, window, sunlight, lens flare,
lens_flare, depth of field, watercolor, watercolor_(medium), painterly, soft lighting,
soft_lighting, detailed background, high detail
```

Lỗi: viết cả tag có dấu cách **và** tag chuẩn (`blue eyes` + `blue_eyes`), lặp ý
(`hair` ⊂ `long_hair`), nhồi tag chất lượng dư (`newest`, `highres`, `very aesthetic`),
mô tả nghệ thuật (`painterly`, `soft_lighting`, `watercolor`) chen giữa chi tiết nhân vật.

**Sau (25 tag, 85 token, 2 cửa sổ, 0 tag bị loãng):**

```
masterpiece, best quality, 1girl, solo, silver long_hair, blue_eyes, smile, open_mouth,
blush, standing, looking_at_viewer, waving, serafuku, red_ribbon, pleated_skirt,
black_kneehighs, loafers, classroom, window, sunlight, BREAK,
watercolor_(medium), painterly, soft_lighting, artist:sample, highres
```

Mẹo đã dùng:

1. **Gộp tag đồng nghĩa** thay vì viết cả hai: `silver long_hair` thay cho
   `long_hair` + `silver_hair` + `straight_hair` (bớt 6 token, không mất thông tin).
2. **BREAK** trước nhóm phong cách → chất liệu màu nước vào **cửa sổ riêng**, không
   tranh trọng số với mô tả nhân vật.
3. **Bỏ tag chất lượng dư** — `masterpiece, best quality` là đủ cho WAI.
4. **Tag < 300 ảnh** (`newest`, `absurdres`…) gần như không tác dụng: xoá để lấy chỗ.

---

## 3. Quy tắc xếp thứ tự (quan trọng hơn độ dài)

Thứ tự app đang dùng (`prompt_lib/groups.py`) đã đúng chuẩn Illustrious:

```
chất lượng → phân loại → mô tả → chủ thể → nhân vật/series → ngoại hình
→ trang phục → biểu cảm/tư thế → hành động → 18+ → đạo cụ → bối cảnh
→ góc máy → phong cách → hoạ sĩ → meta → <lora/embedding>
```

Ba việc cần tự quyết:

- **Chi tiết bắt buộc** (màu tóc, màu mắt, hành động, trang phục chính) phải nằm trong
  **75 token đầu**. Nếu phải chọn giữa "bối cảnh đẹp" và "màu mắt", giữ màu mắt.
- **Phong cách/hoạ sĩ đứng gần cuối** nhưng **trước** vùng loãng (>150 token) nếu bạn
  thật sự cần nó; nếu không thì bỏ.
- **`<lora:...>` luôn ở cuối** — LoRA không chiếm token CLIP theo cách tag thường nhưng
  vẫn nên tách khỏi phần mô tả.

---

## 4. Sáu cách "nhét" thêm chi tiết mà không phá prompt

### 4.1 Bật BREAK giữa các nhóm (dễ nhất)
Trong app: tick **“Chèn BREAK giữa các nhóm”** ở mục *4. Tuỳ chọn prompt*. Mỗi nhóm vào
một cửa sổ riêng, và tag đầu cửa sổ (được chú ý nhất) chính là tag quan trọng của nhóm đó.

### 4.2 Prompt scheduling — thêm chi tiết giữa quá trình sinh
Cú pháp A1111/Forge: `[tag:0.4]` = chỉ bật tag từ bước 40%; `[tag::0.6]` = tắt dần sau 60%.

```
1girl, silver long_hair, classroom, [detailed_background:0.35], [lens_flare:0.5]
```

Chi tiết phụ xuất hiện **sau khi bố cục đã hình thành** → không tranh trọng số với chủ thể.
Dùng 1–2 mục thôi; nhiều hơn sẽ loạn.

### 4.3 Hai lượt: dựng bố cục → thêm chi tiết (hiệu quả nhất với prompt rất dài)
1. **Lượt 1 (txt2img, 832×1216, ~25 bước):** prompt ≤ 75 token, chỉ chủ thể + bố cục + 1
   phong cách. Chọn được ảnh ưng ý → lấy **seed**.
2. **Lượt 2 (img2img hoặc Hires fix, denoise 0.35–0.45):** thêm đúng các chi tiết còn thiếu
   (phụ kiện, hoa văn, đèn, chi tiết nền). Ở denoise thấp, model giữ bố cục và **nhận thêm**
   tag mới mà không cần đọc lại cả prompt dài.

Cách này cho phép "prompt 300 token" mà **không** mất chi tiết, vì mỗi lượt chỉ phải hiểu
≤ 150 token. Đây là khuyến nghị chính khi bạn thật sự có nhiều chi tiết.

### 4.4 Chia vùng không gian (regional)
Forge có extension *Regional Prompter* / *Attention Couple* (tuỳ bản cài): mỗi vùng ảnh một
prompt riêng. Nhân vật bên trái mặc áo dài, bên phải mặc đồng phục → 2 prompt ngắn thay vì
1 prompt dài dễ lẫn. Bộ cài này không cài sẵn extension đó; chỉ dùng khi bạn tự thêm.

### 4.5 Dùng câu mô tả tự nhiên cho quan hệ, tag cho thuộc tính
Illustrious được huấn luyện với caption tự nhiên + tag. Một câu ngắn ở **đầu** prompt
(`a girl kneeling by the window, holding a paper umbrella`) giúp model hiểu **quan hệ**
(vị trí, ai cầm gì) tốt hơn 10 tag rời rạc. Nhưng câu dài 40 từ = ~55 token, ăn gần hết
cửa sổ đầu — nên giữ ≤ 12–15 từ (app có ô *Câu mô tả tiếng Anh* riêng).

### 4.6 Trọng số có kỷ luật
- Chỉ đánh trọng số cho **1–3 chi tiết quan trọng nhất**: `(blue_eyes:1.2)`.
- Không đánh trọng số cho tag chất lượng (`masterpiece`, `best quality`).
- Tránh > 1.4: dễ bết màu, vỡ nét, và ăn token.
- Ngoặc lồng `((tag))` = 1.21, `(((tag)))` = 1.33 — thay bằng `(tag:1.3)` cho rõ ràng.

---

## 5. Việc **không** nên làm

| Không nên | Vì sao |
|---|---|
| Viết cả `blue eyes` và `blue_eyes` | CLIP không hiểu bản có dấu cách như tag; tốn 2–3 token, dễ gây nhiễu |
| Nhồi 6 tag chất lượng | `masterpiece, best quality` là đủ; phần còn lại gần như không đổi ảnh |
| Lặp ý (`hair` + `long_hair` + `straight_hair`) | 1 tag gộp đủ nghĩa, bớt 4–6 token |
| Negative prompt dài 100+ tag | Cùng ngân sách 75 token/cửa sổ; negative dài làm mất luôn chi tiết positive |
| `BREAK` sau mỗi tag | Mỗi cửa sổ chỉ còn 1–2 tag → mất ngữ cảnh, ảnh rời rạc |
| Đặt `watercolor_(medium)` ở đầu | Phong cách sẽ lấn cả bố cục; để gần cuối (trước BREAK cuối) |
| Tăng steps để "model hiểu prompt dài" | Steps chỉ cải thiện độ hoàn thiện, không mở rộng ngữ cảnh CLIP |

---

## 6. Công cụ trong repo

| Công cụ | Ở đâu | Làm gì |
|---|---|---|
| 📏 **Đo độ dài** | App → *Dựng prompt* → mục **📏 Prompt dài** | đếm token, chia cửa sổ 75 token, chỉ ra tag nào rơi vào vùng loãng |
| ✂️ **Nén** | cùng mục | bỏ tag trùng nghĩa (`eyes` khi có `blue_eyes`) và tag lặp, giữ nguyên thứ tự |
| Ghi chú khi dựng prompt | ngay dưới ô Positive | 🟢/🟡/🔴 kèm `N token · M cửa sổ · K tag` + cảnh báo tag bị loãng |
| `Chèn BREAK giữa các nhóm` | *4. Tuỳ chọn prompt* | đặt ranh giới cửa sổ theo nhóm |
| `prompt_lib.limits` | `colab/prompt_lib/limits.py` | `audit_prompt`, `compact_prompt`, `estimate_tokens`, `window_map` — stdlib, test được |

```python
import sys; sys.path.insert(0, "colab")
from prompt_lib.limits import audit_prompt, compact_prompt

rep = audit_prompt(prompt)          # {"tokens": 188, "windows": 3, "late": [...], "advice": [...]}
prompt2, removed = compact_prompt(prompt, group_of=index.group_of)
```

---

## 7. Quy trình gợi ý cho prompt nhiều chi tiết

1. Viết **danh sách chi tiết** bằng tiếng Việt trước (giấy/ghi chú).
2. Chọn **1 chất liệu + 1 kỹ thuật** trong mục *2. Chọn phong cách vẽ*; bấm **Thêm tag phong cách**.
3. Dựng prompt → xem ghi chú độ dài. Nếu 🟢: xong. Nếu 🟡: kiểm tra chi tiết bắt buộc đã ở đầu chưa.
4. Nếu 🔴: tách — **lượt 1** giữ ≤ 75 token (chủ thể + bố cục + phong cách), **lượt 2**
   img2img denoise 0.35–0.45 thêm chi tiết còn lại.
5. Lưu seed ở lượt 1 (nút **🔒 Dùng seed của ảnh đã chọn**), để lượt 2 bám đúng bố cục.
6. Bật **Hires 1.5×, denoise 0.35** cho ảnh cuối; đừng đổi prompt giữa chừng.
