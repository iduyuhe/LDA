"""Generate a branded QR poster for the LDA online store (创新超市)."""
import qrcode
from PIL import Image, ImageDraw, ImageFont
import os

STORE_URL = "https://lda.weomnitech.com.cn/insights.html"
NAME_CN = "LDA 创新超市"
NAME_EN = "LDA Innovation Marketplace"
TAGLINE = "58 货架 · 光子 50 开放下载 · 量子 8 咨询制"
ACCENT = (37, 99, 235)      # #2563eb
DARK = (15, 23, 42)         # #0f172a
MUT = (100, 116, 139)       # #64748b
WHITE = (255, 255, 255)
OUT = os.path.join(os.path.dirname(__file__), "lda_store_qr.png")

W, H = 720, 960
canvas = Image.new("RGB", (W, H), WHITE)
d = ImageDraw.Draw(canvas)

def font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

# Top accent bar
d.rectangle([0, 0, W, 12], fill=ACCENT)

# Store name
f_name = font(56, bold=True)
bbox = d.textbbox((0, 0), NAME_CN, font=f_name)
tw = bbox[2] - bbox[0]
d.text(((W - tw) / 2, 90), NAME_CN, font=f_name, fill=DARK)

# English subtitle
f_en = font(26)
bbox = d.textbbox((0, 0), NAME_EN, font=f_en)
tw = bbox[2] - bbox[0]
d.text(((W - tw) / 2, 170), NAME_EN, font=f_en, fill=MUT)

# QR code
qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=12,
    border=4,
)
qr.add_data(STORE_URL)
qr.make(fit=True)
qr_img = qr.make_image(fill_color=DARK, back_color=WHITE).convert("RGB")
# size QR to ~440px
qs = 440
qr_img = qr_img.resize((qs, qs), Image.LANCZOS)

# center logo box
logo_sz = 96
logo = Image.new("RGB", (logo_sz, logo_sz), WHITE)
ld = ImageDraw.Draw(logo)
ld.rectangle([0, 0, logo_sz - 1, logo_sz - 1], outline=ACCENT, width=4)
f_logo = font(30, bold=True)
bbox = ld.textbbox((0, 0), "LDA", font=f_logo)
lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
ld.text(((logo_sz - lw) / 2, (logo_sz - lh) / 2 - 2), "LDA", font=f_logo, fill=ACCENT)
qx = (W - qs) / 2
qy = 250
canvas.paste(qr_img, (int(qx), int(qy)))
canvas.paste(logo, (int(W / 2 - logo_sz / 2), int(qy + qs / 2 - logo_sz / 2)))

# URL (clickable text)
f_url = font(28, bold=True)
bbox = d.textbbox((0, 0), "lda.weomnitech.com.cn", font=f_url)
tw = bbox[2] - bbox[0]
d.text(((W - tw) / 2, 740), "lda.weomnitech.com.cn", font=f_url, fill=ACCENT)

# Tagline
f_tag = font(22)
bbox = d.textbbox((0, 0), TAGLINE, font=f_tag)
tw = bbox[2] - bbox[0]
d.text(((W - tw) / 2, 800), TAGLINE, font=f_tag, fill=MUT)

# bottom note
f_note = font(18)
note = "扫码进入创新超市 · 前瞻预研设计就绪包"
bbox = d.textbbox((0, 0), note, font=f_note)
tw = bbox[2] - bbox[0]
d.text(((W - tw) / 2, 860), note, font=f_note, fill=MUT)

# bottom accent bar
d.rectangle([0, H - 12, W, H], fill=ACCENT)

canvas.save(OUT)
print("saved", OUT, "size", canvas.size)
