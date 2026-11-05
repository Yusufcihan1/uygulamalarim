"""icon.ico üretir: mor-turkuaz degrade yuvarlak kare üstünde yukarı ok."""
from PIL import Image, ImageDraw

S = 1024
grad = Image.new("RGBA", (S, S))
a, b = (124, 92, 255), (34, 211, 238)
grad.putdata([tuple(int(a[i] + (b[i] - a[i]) * (x + y) / (2 * S)) for i in range(3)) + (255,)
              for y in range(S) for x in range(S)])
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=230, fill=255)
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
d.polygon([(512, 200), (760, 470), (600, 470), (600, 680), (424, 680), (424, 470), (264, 470)], fill="white")
d.rounded_rectangle((264, 760, 760, 840), radius=40, fill="white")

img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
