"""cr.py <src> <dst> <side L|R|F> <y0frac> <y1frac> <outwidth> [x0frac x1frac within half]"""
import sys
from PIL import Image
src, dst, side, y0, y1, ow = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
im = Image.open(src)
W, H = im.size
if side == "L":
    a, b = 0, W // 2 + 40
elif side == "R":
    a, b = W // 2 - 40, W
else:
    a, b = 0, W
if len(sys.argv) > 8:
    x0, x1 = float(sys.argv[7]), float(sys.argv[8])
    a, b = int(a + (b - a) * x0), int(a + (b - a) * x1)
c = im.crop((a, int(H * y0), b, int(H * y1)))
if c.width > ow:
    c = c.resize((ow, int(c.height * ow / c.width)), Image.LANCZOS)
c.save(dst, quality=88)
print(im.size, c.size)
