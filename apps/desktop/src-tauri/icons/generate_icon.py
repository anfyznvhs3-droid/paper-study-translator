"""Generate icon.ico from the app's soft-pink brand (sidebar "QD" mark)."""

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
GRADIENT_START = (255, 138, 203)  # --primary #ff8acb
GRADIENT_END = (185, 146, 255)    # --accent #b992ff


def build_base() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pixels = img.load()
    for y in range(SIZE):
        t = y / (SIZE - 1)
        r = round(GRADIENT_START[0] + (GRADIENT_END[0] - GRADIENT_START[0]) * t)
        g = round(GRADIENT_START[1] + (GRADIENT_END[1] - GRADIENT_START[1]) * t)
        b = round(GRADIENT_START[2] + (GRADIENT_END[2] - GRADIENT_START[2]) * t)
        for x in range(SIZE):
            pixels[x, y] = (r, g, b, 255)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=SIZE // 5, fill=255
    )
    img.putalpha(mask)

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", int(SIZE * 0.42))
    text = "QD"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]),
        text,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return img


if __name__ == "__main__":
    base = build_base()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base.save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print("wrote icon.ico with sizes", sizes)
