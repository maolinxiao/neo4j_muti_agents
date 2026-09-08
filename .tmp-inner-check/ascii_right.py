# -*- coding: utf-8 -*-
"""右半区高分辨率 ASCII 渲染（亮度 + 彩色粗分类）。"""
import sys

import cv2
import numpy as np

path = sys.argv[1]
img = cv2.imread(path)
h, w = img.shape[:2]
# 取右半区
right = img[:, w // 2 :]
H, W = 60, 150
small = cv2.resize(right, (W, H))
hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
v = hsv[:, :, 2]
s = hsv[:, :, 1]
chars = " .:-=+*#%@"
out = []
for y in range(H):
    row = ""
    for x in range(W):
        val = int(v[y, x])
        sat = int(s[y, x])
        # 高饱和亮色（卫星/彩光）用字母标记
        if val > 140 and sat > 60:
            hue = int(hsv[y, x, 0])
            c = "G" if hue < 45 else ("C" if hue < 100 else ("B" if hue < 130 else ("M" if hue < 160 else "R")))
            row += c
        else:
            row += chars[min(len(chars) - 1, val * len(chars) // 256)]
    out.append(row)
print("\n".join(out))
