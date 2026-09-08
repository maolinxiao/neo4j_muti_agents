# -*- coding: utf-8 -*-
"""ASCII 可视化：把帧缩到 ~140x79 打印灰度字符画（帮助无视觉模型时“目检”）。"""
import sys

import cv2
import numpy as np

path = sys.argv[1]
img = cv2.imread(path)
h, w = img.shape[:2]
W, H = 140, 78
small = cv2.resize(img, (W, H))
gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
chars = " .:-=+*#%@"
out = []
for y in range(H):
    row = ""
    for x in range(W):
        v = int(gray[y, x])
        row += chars[min(len(chars) - 1, v * len(chars) // 256)]
    out.append(row)
print("\n".join(out))
