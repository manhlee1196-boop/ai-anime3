"""Phân loại tag vào các nhóm và xếp thứ tự prompt theo chuẩn Illustrious/WAI.

Quy ước cộng đồng (đã kiểm chứng):
- Illustrious/WAI: cho phép "lai" — một câu mô tả ngắn rồi tới tag Danbooru,
  cuối cùng là tag chất lượng.
- NoobAI/Illustrious: tag chất lượng đứng đầu cho kết quả ổn định hơn.
Bộ dựng prompt xếp theo: [câu mô tả] + chất lượng + phân loại + nguồn + số lượng/chủ thể
+ nhân vật + series + cốt truyện + loài + ngoại hình + trang phục + biểu cảm + tư thế
+ hành động + 18+ + đạo cụ + bối cảnh + góc máy + hoạ sĩ + meta + còn lại.
"""

import re

# Thứ tự nhóm khi ghép prompt (trái -> phải)
GROUP_ORDER = [
    "quality", "rating", "source", "subject", "character", "copyright", "lore",
    "species", "appearance", "clothing", "expression", "pose", "action",
    "sexual", "object", "background", "camera", "artist", "meta", "negative",
    "other",
]

GROUP_LABELS = {
    "quality":    "Chất lượng",
    "rating":     "Phân loại nội dung",
    "source":     "Nguồn / phong cách",
    "subject":    "Số lượng & chủ thể",
    "character":  "Nhân vật",
    "copyright":  "Series / bản quyền",
    "lore":       "Cốt truyện (e621)",
    "species":    "Loài",
    "appearance": "Ngoại hình & cơ thể",
    "clothing":   "Trang phục & phụ kiện",
    "expression": "Biểu cảm",
    "pose":       "Tư thế",
    "action":     "Hành động",
    "sexual":     "18+",
    "object":     "Đạo cụ & vật thể",
    "background": "Bối cảnh & nền",
    "camera":     "Góc máy & khung hình",
    "artist":     "Hoạ sĩ",
    "meta":       "Meta (chữ, viền, chú thích...)",
    "negative":   "Hay dùng cho negative",
    "other":      "Khác",
}

# Nhóm chỉ để duyệt thư viện, không sinh ra từ tag nội dung
BROWSE_GROUPS = [g for g in GROUP_ORDER if g not in ("quality", "rating", "negative")]

# Category của file merged -> nhóm mặc định (không cần đoán bằng từ khoá)
CAT_GROUP = {
    1: "artist", 8: "artist",
    3: "copyright", 9: "copyright",
    4: "character", 10: "character", 11: "character",
    5: "meta", 14: "meta",
    12: "species",
    15: "lore",
}

# Tiền tố namespace mà NoobAI/Forge hỗ trợ: artist:, character:, copyright: ...
_NAMESPACE_RE = re.compile(r"^(artist|character|copyright|species|meta|general):")
_NAMESPACE_GROUP = {
    "artist": "artist", "character": "character", "copyright": "copyright",
    "species": "species", "meta": "meta", "general": "other",
}

# Nhóm suy ra từ từ khoá, kiểm tra theo thứ tự (khớp trước thắng).
# Tag được đưa về dạng có khoảng trắng nên pattern cũng viết bằng khoảng trắng.
_KEYWORDS = [
    ("subject", [
        r"^\d+ ?(girl|boy|girls|boys|others)$", r"^solo", r"^duo$", r"^trio$", r"^no humans$",
        r"^multiple ", r"^crowd$", r"^group$", r"^background characters$",
        r"^human$", r"^humanoid$", r"^furry$", r"^female$", r"^male$", r"^both ",
        r"^yuri$", r"^yaoi$", r"^hetero$", r"^ambiguous gender$", r"^interspecies$",
        r"^intersex$", r"^size difference$", r"^male/female$", r"^male/male$",
        r"^female/female$", r"^1others$", r"^2others$",
    ]),
    ("camera", [
        r"close[- ]up", r"^portrait", r"upper body", r"full body", r"cowboy shot",
        r"wide shot", r"long shot", r"establishing shot", r"from above", r"from below",
        r"from side", r"from behind", r"from back", r"straight[- ]on", r"dutch angle",
        r"^pov", r"depth of field", r"^bokeh", r"^blurry", r"^fisheye", r"^selfie",
        r"angle$", r"^cropped", r"out of frame", r"^sideways$", r"dynamic angle",
        r"^macro$", r"^panorama", r"framing", r"^shot$", r"head shot", r"^eye level",
        r"low angle", r"high angle", r" focus$", r"^male focus$", r"^female focus$",
        r"^profile$", r"^rear$", r"^zoom",
    ]),
    ("expression", [
        r"smil", r"smirk", r"grin", r"blush", r"^cry", r"crying", r"tears", r"angry",
        r"^sad", r"happy", r"surprised", r"expression", r"open mouth", r"closed mouth",
        r"closed eyes", r"one eye closed", r"wink", r"frown", r"pout", r"embarrass",
        r"nervous", r"sleepy", r"bored", r"laughing", r"screaming", r"^doyagao",
        r"flustered", r"^scowl", r"wide eyes", r"expressionless", r"parted lips",
        r"tongue out", r"^tongue$", r"sweatdrop", r"^:3$", r"^\^ \^$", r"^> <$",
        r"^:d$", r"^xd$", r"emoticon", r"^o o$", r"^crying with eyes open$",
        r"^empty eyes$", r"^glowing eyes$", r"^half-closed eyes$", r"^no eyes$",
    ]),
    ("pose", [
        r"^standing", r"^sitting", r"^lying", r"^kneeling", r"^crouching", r"^leaning",
        r"^bending", r"^stretching", r"^walking", r"^running", r"^jumping", r"^falling",
        r"^floating", r"^sleeping", r"^reclining", r"^squatting", r"on back", r"on side",
        r"on stomach", r"^spread", r"arms up", r"arms behind", r"arms crossed",
        r"crossed legs", r"hand on ", r"hands on ", r"^looking ", r"^facing ",
        r"^all fours", r"^prone", r"^bathing", r"^swimming", r"^climbing", r"^crawling",
        r"^laying", r"^seiza", r"^wariza", r"^yokozuwari", r"^hunched", r"^upright",
        r"^bent over", r"^on one knee", r"^crossed arms",
        r"^arm support", r"^head tilt", r"^head rest", r"^shrugging",
    ]),
    ("action", [
        r"^holding", r"^wielding", r"^eating", r"^drinking", r"^cooking", r"^playing",
        r"^singing", r"^dancing", r"^reading", r"^writing", r"^fighting", r"^shooting",
        r"^driving", r"^riding", r"^hugging", r"^kissing", r"^licking", r"^biting",
        r"^grabbing", r"^touching", r"^pointing", r"^waving", r"^throwing", r"^catching",
        r"^carrying", r"^lifting", r"^pushing", r"^pulling", r"^cutting", r"^smoking",
        r"^painting", r"^drawing", r"^typing", r"^using ", r"^aiming", r"^casting",
        r"^wearing", r"^dressing", r"^undressing", r"^applying ", r"^cleaning",
        r"^washing", r"^praying", r"^saluting", r"^cheering", r"^training",
    ]),
    ("sexual", [
        r"^sex\b", r" sex\b", r"^nude$", r"^naked", r"nipples?", r"^areola",
        r"pussy", r"penis", r"penile", r"^erection", r"handjob", r"fellatio",
        r"cunnilingus", r"paizuri", r"penetrat", r"orgasm", r"masturbat", r"bondage",
        r"^bdsm", r"rape", r"^incest", r"^ahegao", r"ass grab", r"breast grab",
        r"^groping", r"^stripping$", r"panties (around|aside|down)", r"^cum",
        r"^gag$", r"^leash$", r"^chastity", r"^frottage", r"^tribadism", r"^rimming$",
        r"^footjob$", r"^erotic", r"^hentai", r"^nsfw", r"^explicit", r"sexual",
        r"^coitus", r"^missionary", r"^cowgirl position", r"^doggy ?style",
        r"^doggystyle$", r"^suspended congress", r"^mating press", r"genitals?",
        r"^anus$", r"anal", r"^vulva$", r"vaginal", r"^vagina", r"^balls$",
        r"ejaculation", r"^oral$", r"genital fluids", r"^presenting",
        r"^clothed sex", r"^uncensored$", r"^cameltoe$", r"^areolae$",
        r"^erection under clothes$", r"^nipple slip", r"^clothed masturbation",
        # Ghi chú: cỡ ngực/mông (breasts, big ass...) thuộc nhóm Ngoại hình,
        # không phải 18+, vì chúng xuất hiện cả trong ảnh an toàn.
    ]),
    ("species", [
        r"^anthro$", r"^feral$", r"^biped$", r"^taur$", r" taur$", r"^semi-anthro$",
        r"^mythological creature$", r"^dragon$", r"^dragon ", r" dragon$", r"^fox$",
        r"^wolf$", r"^rabbit$", r"^bunny$", r"^bird$", r"^cat$", r"^dog$", r"^horse$",
        r"^deer$", r"^snake$", r"^fish$", r"^shark$", r"^bear$", r"^lion$",
        r"^tiger$", r"^elephant$", r"^mouse$", r"^rat$", r"^cow$", r"^sheep$",
        r"^goat$", r"^pig$", r"^boar$", r"^monkey$", r"^ape$", r"^owl$", r"^eagle$",
        r"^crow$", r"^raven$", r"^duck$", r"^goose$", r"^swan$", r"^frog$",
        r"^lizard$", r"^turtle$", r"^dinosaur$", r"^insect$", r"^butterfly$",
        r"^bee$", r"^spider$", r"^scorpion$", r"^bat$", r"^whale$", r"^dolphin$",
        r"^seal$", r"^otter$", r"^raccoon$", r"^panda$", r"^kangaroo$", r"^unicorn$",
        r"^griffin$", r"^phoenix$", r"^mermaid$", r"^centaur$", r"^kitsune$",
        r"^kemonomimi$", r"^catgirl$", r"^dog girl$", r"^cat girl$", r"^furry$",
        r"^pokemon$", r"^pokemon \(creature\)$", r"^monster$", r"^slime$",
        r"^demon$", r"^angel$", r"^vampire$", r"^werewolf$", r"^zombie$",
        r"^ghost$", r"^elf$", r"^dwarf$", r"^orc$", r"^goblin$", r"^kobold$",
        r"^lizardman$", r"^minotaur$", r"^satyr$", r"^harpy$", r"^sphinx$",
        r"^(cat|dog|fox|wolf|bunny|rabbit|bear|cow|sheep|pig|mouse|rat|dragon|bird"
        r"|snake|horse|deer|tiger|lion|bat|shark|owl|fox) (girl|boy)$",
        r"^kemono", r"^animal$", r"^creature$", r"^species$", r"^canine$", r"^feline$",
        r"^equine$", r"^avian$", r"^reptile$", r"^amphibian$", r"^arthropod$",
        r"^mollusk$", r"^crustacean$", r"^hybrid$", r"^chimera$", r"^yokai$",
        r"^oni$", r"^tengu$", r"^kappa$", r"^tanuki$", r"^nekomata$",
    ]),
    ("object", [
        r"^sword", r"^weapon", r"^gun", r"^knife", r"^dagger", r"^spear", r"^axe",
        r"^shield", r"^staff", r"^wand", r"^book", r"^phone", r"^umbrella", r"^cup",
        r"^bottle", r"^food", r"^cake", r"^bag$", r"^box$", r"^instrument",
        r"^guitar", r"^violin", r"^piano", r"^fan$", r"^handheld", r"^orb$",
        r"^scroll", r"^letter", r"^envelope", r"^coin", r"^jewel", r"^gem$",
        r"^toy$", r"^ball$", r"^balloon", r"^cigarette", r"^drink", r"^tea$",
        r"^coffee", r"^bento", r"^onigiri", r"^ramen", r"^apple$", r"^flower bouquet",
        r"^bouquet", r"^vehicle", r"^car$", r"^motorcycle", r"^bicycle", r"^boat$",
        r"^airplane", r"^scythe", r"^hammer", r"^bow and arrow", r"^arrow$",
        r"^magic circle", r"^potion", r"^lantern$", r"^candle$", r"^mirror$",
        r"^pillow$", r"^blanket$", r"^phone$", r"^laptop", r"^computer", r"^camera$",
        r"^microphone", r"^headphones", r"^glasses case", r"^cane$", r"^crutch",
        r"^wheelchair", r"^musical instrument", r"^drum$", r"^flute$",
    ]),
    ("appearance", [
        r"hair", r"eyes?", r"eye ", r"^breast", r"thighs?", r"skin", r"^body",
        r" body$", r"tail", r"ears?", r"horns?", r"wings?", r"fangs?", r"teeth",
        r"nails?", r"muscle", r"height", r"^tall", r"^short ", r"^child$", r"^teen",
        r"^adult", r"^old ", r"^young", r"freckles", r"^mole", r"scar", r"tattoo",
        r"piercing", r"belly", r"navel", r"cleavage", r"hips?", r"waist", r"legs?",
        r"arms?", r"hands?", r"^feet$", r"^foot$", r"fingers?", r"^face$",
        r"facial ", r"head ", r"^bald", r"^ponytail", r"^twintails", r"^braid",
        r"^bangs", r" bangs$", r"^ahoge", r"^heterochromia", r"^pupils?",
        r"^eyelashes", r"^makeup", r"^lipstick", r"^muscular", r"^slim", r"^plump",
        r"^fat$", r"^thin$", r" fur$", r"scales", r"feathers", r"^fluffy",
        r"^sweat", r"^toes", r"^claws", r"markings", r"^stomach", r"^abs$",
        r"^paws", r"^pawpads", r" nose$", r"^tuft", r"sidelocks", r"^saliva",
        r"^muzzle", r"^snout", r"^whiskers", r"^mane$", r"^bare shoulders",
        r"^bare legs", r"^bare arms", r"^bare back", r"^barefoot", r"^midriff",
        r"^bare midriff", r"^mole ", r"^birthmark", r"^freckles$", r"^veins",
        r"^saliva trail", r"^tongue piercing", r"^ear piercing", r"^nose piercing",
        r"^body writing", r"^tan$", r"^tanlines", r"^pale skin", r"^dark skin",
        r"^oiled body", r"^wet body", r"^wet hair", r"^wet clothes",
        # cỡ/người thật của bộ phận cơ thể: xếp Ngoại hình chứ không phải 18+
        r"^breasts?$", r"^breast ", r" breasts$", r"^flat chest$", r"^ass$",
        r"^big ass$", r"^huge ass$", r"^butt$", r"^big butt$", r"^huge butt$",
        r"^thick thighs$", r"^long legs$",
    ]),
    ("clothing", [
        r"shirt", r"dress", r"skirt", r"pants", r"shorts", r"bikini", r"swimsuit",
        r"uniform", r"jacket", r"coat", r"hoodie", r"sweater", r"gloves?", r"socks?",
        r"stockings?", r"shoes?", r"boots?", r"^hat", r"^cap$", r"^bra$", r"panties",
        r"underwear", r"lingerie", r"kimono", r"yukata", r"armor", r"^suit$",
        r"^suits$", r"^tie$", r"necktie", r"ribbon", r"scarf", r"belt", r"jewelry",
        r"^ring$", r"necklace", r"earrings?", r"glasses", r"^maid", r"apron",
        r"sailor", r"serafuku", r"cape", r"cloak", r"veil", r"^mask$", r"collar",
        r"choker", r"garter", r"leggings", r"footwear", r"clothes", r"^clothing$",
        r"^clothed", r"costume", r"outfit", r"^hood$", r"sleeves?", r"slippers",
        r"sandals", r"heels", r"^crown$", r"headwear", r"^helmet", r"hairband",
        r"hair ornament", r"hairclip", r"hairclip", r"bowtie", r"^bow$", r" bow$",
        r"suspenders", r"^vest$", r"^cardigan", r"^nightgown", r"^robe$", r"^tunic",
        r"^hakama", r"^fundoshi", r"^sarong", r"^ao dai", r"^ao yem", r"^non la",
        r"conical hat", r"vietnamese clothes", r"vietnamese high school uniform",
        r"^cheongsam", r"^hanbok", r"^hanfu", r"^wedding dress", r"^wedding gown",
        r"^school swimsuit", r"^buruma", r"^bloomers", r"^leotard", r"^bodysuit",
        r"^jumpsuit", r"^overalls", r"^poncho", r"^raincoat", r"^trench coat",
        r"^blazer", r"^turtleneck", r"^camisole", r"^crop top", r"^tube top",
        r"^halterneck", r"pantyhose", r"^frills", r"^off shoulder", r"^halo$",
        r"^accessory", r"^ornament", r"^bracelet", r"^armband", r"^gloves$",
        r"^thong$", r"^strapless", r"^plunging neckline", r"^cleavage cutout",
        r"^side slit", r"^backless", r"^fur trim", r"^lace trim", r"^tassel",
        r"^badge$", r"^brooch$", r"^pendant$", r"^chain$", r"^piercing$",
        r"^eyepatch", r"^sunglasses", r"^monocle", r"^visor$", r"^goggles",
    ]),
    ("background", [
        r"background", r"outdoors", r"indoors", r"^sky$", r"clouds?", r"forest",
        r"^trees?", r"beach", r"^sea$", r"ocean", r"river", r"mountains?", r"^city",
        r"street", r"^room", r"bedroom", r"^school", r"castle", r"^night$", r"^day$",
        r"sunset", r"sunrise", r"^rain", r"^snow", r"flowers?", r"^grass$",
        r"^field$", r"^park$", r"library", r"cafe", r"^train", r"^space$",
        r"^stars?", r"^moon$", r"^sun$", r"^fog$", r"^mist$", r"cityscape",
        r"landscape", r"scenery", r"^water$", r"^lake$", r"^island$", r"^bridge$",
        r"^church$", r"^temple$", r"^shrine$", r"^garden$", r"^rooftop$",
        r"^window$", r"^door$", r"^wall$", r"^floor$", r"^ceiling$", r"^stairs?",
        r"^bed$", r"^chair$", r"^table$", r"^desk$", r"^bookshelf$", r"^kitchen$",
        r"^bathroom$", r"^bathtub$", r"^pool$", r"^stage$", r"^ruins$", r"^dungeon$",
        r"^cave$", r"^season ", r"^autumn$", r"^spring$", r"^summer$", r"^winter$",
        r"^weather ", r"^cloudy$", r"^storm$", r"^lightning$", r"^rainbow$",
        r"^aurora$", r"^cherry blossoms$", r"^petals$", r"^falling leaves$",
        r"^fountain$", r"^lighthouse$", r"^harbor$", r"^dock$", r"^pier$",
        r"^cliff", r"^valley$", r"^waterfall$", r"^hot spring", r"^onsen",
        r"^classroom", r"^hallway$", r"^gym$", r"^office$", r"^hospital$",
        r"^shop$", r"^store$", r"^restaurant$", r"^bar$", r"^club$", r"^concert$",
        r"^festival$", r"^market$", r"^village$", r"^town$", r"^alley$", r"^road$",
        r"^path$", r"^sidewalk$", r"^crosswalk$", r"^torii$", r"^lantern",
        r"^night sky", r"^starry sky", r"^cloudy sky", r"^blue sky", r"^dusk$",
        r"^dawn$", r"^midnight$", r"^outside$", r"^inside$", r"^plant",
        r"^furniture", r"^simple background", r"^white background",
        r"^transparent background", r"^blurry background", r"^scenery$",
        r"^city lights", r"^neon lights", r"^sunbeam", r"^light rays",
        r"^god rays", r"^backlight", r"^shadow", r"^darkness$", r"^candlelight",
        r"^moonlight", r"^sunlight", r"^glowing", r"^sparkles", r"^bubbles",
        r"^steam", r"^smoke", r"^flames", r"^fire", r"^ice$", r"^bamboo",
        r"^desert", r"^leaves", r"^wheat field", r"^rice paddy", r"^greenhouse",
    ]),
    ("source", [
        r"^chibi", r"^virtual youtuber", r"^vtuber", r"anime screencap", r"^3d$",
        r"^3d background", r"^2d$", r"^pixel art", r"^watercolor", r"^oil painting",
        r"^sketch$", r"^lineart$", r"^cartoon$", r"^comic$", r"^manga$",
        r"^anthropomorphization", r"^realistic$", r"^photorealistic",
        r"^art nouveau", r"^impressionism", r"^ukiyo-e", r"^sumi-e",
    ]),
    ("meta", [
        r" text$", r"^text", r"^english text", r"^japanese text", r"^chinese text",
        r"^korean text", r"^vietnamese text", r"speech bubble", r"^dialogue",
        r"^commentary", r"^translation request", r"^twitter ", r"^username",
        r"^border", r"^watermark", r"^signature", r"^artist name", r"^copyright name",
        r"^logo$", r"^censored", r"^mosaic censoring", r"^bar censor",
        r"^light censoring", r"^self censor", r"^uncensored$", r"^alternate version",
        r"^what if", r"^aged up", r"^aged down", r"^genderbend", r"^source request",
        r"^commentary request", r"^annotation", r"^revision$", r"^parent post",
        r"^child post", r"^variant$", r"^offical$", r"^official alternate version",
    ]),
]

# Tag được so ở dạng đã thay "_" bằng khoảng trắng, nên pattern cũng phải vậy.
_PATTERNS = {group: [re.compile(p.replace("_", " ")) for p in pats]
             for group, pats in _KEYWORDS}

# Vòng pattern bổ sung: các tag e621 và dạng "màu/tính từ + danh từ" mà vòng trên
# bỏ sót (ví dụ "black hat" không khớp "^hat"). Nối vào để khỏi sửa khối lớn ở trên.
_EXTRA = {
    "appearance": [
        r"^fur$", r"^blood$", r"^wet$", r"^veins?$", r"^lips$", r"^pecs$", r"^soles$",
        r"^toe claws$", r"^\d+ ?toes$", r"^countershading$", r"braids$", r"side up$",
        r"braid$", r"pupils$", r"^overweight$", r"^chubby", r"slightly chubby",
        r"^glistening$", r"^sparkle", r"^drooling", r"^dripping", r"^hyper$",
        r"^spikes$", r"^spike ", r" spike$", r"^muscular$", r"^skinny$",
        r"^mature ", r"^elderly$",
        # (loli / shota thuộc nhóm Chủ thể, xét ở độ ưu tiên cao hơn nên không kê ở đây)
    ],
    "clothing": [
        r"^neckerchief$", r"clothing cutout", r" hats?$", r"^wrist cuffs$",
        r"^buttons$", r" button$", r"^ascot$", r"^sash$", r"^tank top$", r" tops?$",
        r"^cosplay$", r"^bottomless$", r"^topless$", r"^underboob$", r"^sideboob$",
        r"^belt buckle$", r"^buckle$", r"^straps?$", r" straps$", r"^trim$",
        r"^cuffs?$", r"^collarbone$", r"^neckwear$", r"^neck ribbon$",
        r"^hair ribbon$", r"^hair flower$", r"^hair bow$", r"^tiara$",
        r"^armlet$", r"^anklet$", r"^brooch$", r"^piercings$",
    ],
    "sexual": [
        r"bodily fluids", r"^precum$", r"^knot$", r"^bulge$", r"^sheath$",
        r"^groin$", r"^big balls$", r"completely nude", r"^bound$", r"^submissive$",
        r"^dominant$", r"^seductive$", r"^bondage$", r"^shibari$", r"^handcuffs$",
        r"^spread legs$", r"^ass up$",
        r"^nude$", r"^topless ", r"^bottomless ", r"^erection$", r"^phimosis$",
        r"^foreskin$", r"^glans$", r"^urethra", r"^cloaca$", r"^pussy juice",
        r"^after sex$", r"^afterglow$", r"^post-coital$",
    ],
    "expression": [
        r"^:o$", r"^v$", r"^:q$", r"^:p$", r"^uwu$", r"^owo$", r"^\^o\^$",
        r"^o o$", r"^- -$", r"^>o<$", r"^expression$", r"^smug$", r"^yandere$",
    ],
    "subject": [
        r"^anthro on anthro$", r"^gynomorph$", r"^andromorph$",
        r"^hermaphrodite$", r"^not furry$", r"^siblings$", r"^family$",
        r"^femboy$", r"^tomboy$", r"^twins$", r"^couple$", r"^pair$",
        r"^shota$", r"^loli$",
    ],
    "species": [
        r"^robots?$", r"^android$", r"^cyborg$", r"^mecha$", r"^monster girl$",
        r"^kaiju$", r"^dragon girl$", r"^dragon boy$", r"^fennec$", r"^husky$",
        r"^protogen$", r"^sergal$", r"^avian anthro$", r"^scalie$",
    ],
    "pose": [
        r"^on bed$", r"^pose$", r"^poses$", r"^posing$", r"^front view$",
        r"^side view$", r"^back view$", r"^ass up$", r"^face down$",
        r"^head down$", r"^head up$", r"^leaning forward$", r"^leaning back$",
        r"^arched back$", r"^outstretched ", r"^hands up$", r"^hand up$",
        r"^arm up$", r"^leg up$", r"^legs up$", r"^knees up$",
    ],
    "action": [
        r"^hug$", r"^hugs$", r"^kiss$", r"^pat$", r"^patting$", r"^headpat$",
        r"^handhold$", r"^holding hands$", r"^high five$", r"^fist bump$",
        r"^spanking$", r"^slap$", r"^punch$", r"^kick$", r"^swing$", r"^spin$",
        r"^turning$", r"^looking back$", r"^glaring$", r"^staring$", r"^gazing$",
    ],
    "object": [
        # ribbon / chain / flowers để cho Trang phục & Bối cảnh bắt
        # (nhóm Đạo cụ có độ ưu tiên cao hơn nên không được kê ở đây)
        r"^bell$", r"^fruit$", r"^umbrella$", r"^parasol$",
        r"^weapon$", r"^dagger$", r"^katana$", r"^spear$", r"^whip$",
        r"^rope$", r"^present$", r"^gift$", r"^teddy bear$",
        r"^plushie$", r"^doll$", r"^kite$", r"^frisbee$", r"^skateboard$",
        r"^surfboard$", r"^snowboard$", r"^skis$", r"^fishing rod$",
        r"^paintbrush$", r"^pen$", r"^pencil$", r"^notebook$", r"^scroll$",
    ],
    "background": [
        r"^on bed$", r"^bed$", r"^bedroom$", r"^inside$", r"^outside$",
        r"^scenery$", r"^nature$", r"^flowers$", r"^roses$", r"^petals$",
        r"^grass$", r"^bushes$", r"^hedge$", r"^tree$", r"^pine tree$",
        r"^palm tree$", r"^ocean$", r"^waves$", r"^shore$", r"^sand$",
        r"^snow$", r"^snowing$", r"^raining$", r"^cloudy$", r"^sunny$",
        r"^starry$", r"^night$", r"^day$", r"^indoors$", r"^outdoors$",
    ],
    "camera": [
        r"^front view$", r"^side view$", r"^back view$", r"^top down$",
        r"^bottom up$", r"^wide$", r"^close$", r"^distant$", r"^full shot$",
        r"^half body$", r"^bust shot$", r"^face shot$", r"^legs shot$",
        r"^ass shot$", r"^hip shot$", r"^knee shot$", r"^waist shot$",
    ],
    "source": [
        r"^\d{4}$", r"^\d{4}s$", r"^early$", r"^late$", r"^mid-", r"^2000s$",
        r"^1990s$", r"^1980s$", r"^showa$", r"^heisei$", r"^reiwa$",
    ],
    "meta": [
        r" border$", r"^dated$", r"character name", r"sound effects",
        r"motion lines", r"^speed lines$", r"^name tag$", r"^subtitle$",
        r"^caption$", r"^title$", r"^logo$", r"^copyright notice$",
        r"^sample$", r"^thumbnail$", r"^cover$", r"^page number$",
        r"^4koma$", r"^comic$", r"^manga$", r"^silent comic$", r"^animated$",
        r"^loop$", r"^video$", r"^incomplete$", r"^ai-generated$", r"^ai assisted$",
        r"^absurdly long ", r"^alternate costume$", r"^alternate hairstyle$",
        r"^alternate ",
    ],
}
for _g, _pats in _EXTRA.items():
    _PATTERNS.setdefault(_g, []).extend(
        re.compile(p.replace("_", " ")) for p in _pats)

# Độ ưu tiên xét nhóm, TÁCH KHỎI thứ tự khai báo ở trên để dễ chỉnh.
# Ví dụ: "dragon" -> Loài, nhưng "dragon_tail" phải là Ngoại hình (xét Ngoại hình
# trước Loài); "white_shirt" phải là Trang phục nên KHÔNG xét theo màu.
# "sexual" phải xét TRƯỚC "pose"/"action": nếu không thì licking_penis, holding_penis,
 # breast_grab... sẽ bị hai nhóm kia bắt mất vì chúng cũng khớp "^licking", "^holding".
# Ngược lại cỡ ngực/mông (large_breasts, big_ass) đã bị gỡ khỏi nhóm sexual nên vẫn
# rơi đúng vào "appearance".
_PRIORITY = [
    "subject", "camera", "expression", "sexual", "pose", "action", "object",
    "appearance", "clothing", "species", "background", "source", "meta",
]
_COMPILED = [(group, _PATTERNS[group]) for group in _PRIORITY]


def strip_namespace(tag):
    """Bỏ tiền tố `artist:` / `character:` ... để phân loại đúng tag gốc."""
    return _NAMESPACE_RE.sub("", tag.strip())


def namespace_group(tag):
    """Nếu tag có tiền tố namespace thì trả về nhóm tương ứng, ngược lại None."""
    m = _NAMESPACE_RE.match(tag.strip())
    return _NAMESPACE_GROUP.get(m.group(1)) if m else None


def classify(tag, category=None, system_group=None):
    """Trả về tên nhóm của một tag."""
    if system_group:
        return system_group
    ns = namespace_group(tag)
    if ns:
        return ns
    t = strip_namespace(tag).strip().lower()
    spaced = t.replace("_", " ")
    if category is not None and category in CAT_GROUP:
        return CAT_GROUP[category]
    for group, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(spaced):
                return group
    return "other"


def sort_groups(groups):
    """Sắp xếp tên nhóm theo đúng thứ tự prompt chuẩn."""
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    return sorted(groups, key=lambda g: order.get(g, 99))
