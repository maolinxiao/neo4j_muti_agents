# -*- coding: utf-8 -*-
"""按指定中心/半径打印局部精细 ASCII（亮度+饱和色分类）。"""
import sys

import cv2
import numpy as np

path, cx, cy, r = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
img = cv2.imread(path)
img = cv2.resize(img, (960, 540))
pad = int(r * 1.9)
x0, x1 = max(0, cx - pad), min(960, cx + pad)
y0, y1 = max(0, cy - pad), min(540, cy + pad)
crop = img[y0:y1, x0:x1]
H, W = 46, 120
small = cv2.resize(crop, (W, H))
hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
chars = " .:-=+*#%@"
for y in range(H):
    row = ""
    for x in range(W):
        val = int(hsv[y, x, 2])
        sat = int(hsv[y, x, 1])
        if val > 110 and sat > 60:
            hue = int(hsv[y, x, 0])
            row += "G" if hue < 45 else ("C" if hue < 100 else ("B" if hue < 130 else ("M" if hue < 160 else "R")))
        else:
            row += chars[min(len(chars) - 1, val * len(chars) // 256)]
    print(row)
