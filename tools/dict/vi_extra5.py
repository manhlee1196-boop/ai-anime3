"""Đợt từ vựng 5 — chú thích cho TỪ MƯỢN và tag liên quan Việt Nam.

Vấn đề: nhiều từ mượn mà tiếng Việt dùng nguyên văn (bikini, kimono, chibi, meme...)
có bản dịch trùng khít với tag, nên theo quy tắc "chỉ ghi dòng có dịch thật" chúng bị
loại khỏi file translation. Hệ quả là người dùng Việt gõ "đồ bơi" không tìm ra bikini.

Cách xử lý: thêm phần giải thích trong ngoặc, giống cách đã làm với emoticon
(`:3` -> ":3 (miệng mèo cười)"). Nhờ đó bản dịch khác tag gốc và tag trở lại
file translation, đồng thời tra cứu được bằng từ tiếng Việt tương đương.
"""

# ---------------------------------------------------------------- cat 0 (Danbooru)
VI_EXTRA_GENERAL_5 = {
    # trang phục / đồ bơi
    "bikini":       "bikini (đồ bơi hai mảnh)",
    "kimono":       "kimono (trang phục truyền thống Nhật)",
    "hakama":       "hakama (quần váy Nhật)",
    "yukata":       "yukata (kimono mặc mùa hè)",
    "obijime":      "obijime (dây buộc thắt lưng kimono)",
    "happi":        "happi (áo khoác lễ hội Nhật)",
    "waraji":       "waraji (dép rơm Nhật)",
    "furoshiki":    "furoshiki (khăn bọc đồ Nhật)",
    "hanbok":       "hanbok (trang phục truyền thống Hàn)",
    "conical_hat":  "nón chóp (nón lá)",

    # Việt Nam
    "ao_dai":                        "áo dài",
    "vietnamese_clothes":            "trang phục Việt Nam",
    "vietnamese_high_school_uniform": "đồng phục nữ sinh Việt Nam",
    "vietnamese_flag":               "cờ Việt Nam",
    "vietnam_war":                   "chiến tranh Việt Nam",

    # phong cách / thể loại
    "chibi":        "chibi (vẽ đầu to người nhỏ)",
    "meme":         "meme (ảnh chế)",
    "mecha":        "mecha (robot chiến đấu)",
    "tokusatsu":    "tokusatsu (phim kỹ xảo đặc biệt của Nhật)",
    "otaku":        "otaku (người mê anime)",
    "yandere":      "yandere (yêu đến mức cực đoan)",
    "tsundere":     "tsundere (ngoài lạnh trong nóng)",
    "kuudere":      "kuudere (lạnh lùng ít nói)",

    # võ sĩ / vũ khí Nhật
    "ninja":        "ninja (nhẫn giả)",
    "samurai":      "samurai (võ sĩ Nhật)",
    "geisha":       "geisha (nghệ giả Nhật)",
    "shuriken":     "shuriken (phi tiêu hình sao)",
    "naginata":     "naginata (kích thương Nhật)",
    "wakizashi":    "wakizashi (đoản kiếm Nhật)",

    # ẩm thực / trò chơi
    "sushi":        "sushi (cơm cuộn cá sống)",
    "tofu":         "tàu hũ (đậu phụ)",
    "mahjong":      "mahjong (mạt chược)",

    # đồ vật khác
    "noren":        "noren (rèm treo cửa hiệu Nhật)",

    # tag thường dùng cho negative prompt, kho chính có tag nhưng chưa dịch
    "sensitive":       "nhạy cảm",
    "bad_proportions": "tỷ lệ cơ thể sai",
    "extra_digits":    "thừa ngón",
    "fewer_digits":    "thiếu ngón",
    "extra_limbs":     "thừa tay chân",
    "missing_limbs":   "thiếu tay chân",
    "fused_fingers":   "ngón tay dính nhau",
    "disfigured":      "méo mó",
    "mutated":         "dị tật",
}

# ---------------------------------------------------------------- cat 7 (e621)
VI_EXTRA_E621_5 = {
    "zori":               "zori (dép quai kẹp Nhật)",
    "asian_conical_hat":  "nón lá châu Á",
}
