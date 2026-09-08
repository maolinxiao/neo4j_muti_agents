# -*- coding: utf-8 -*-
"""右半区（纯 3D 场景区）跨帧差异：判断场景是否冻结。"""
import glob
import os

import cv2
import numpy as np

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
frames = sorted(glob.glob(os.path.join(SHOTS, "frame_*.png")))
prev = None
for f in frames:
    img = cv2.imread(f)
    img = cv2.resize(img, (960, 540))
    right = img[:, 500:].astype(np.int16)  # 右半区（避开左文案区）
    if prev is not None:
        d = float(np.abs(right - prev).mean())
        print(os.path.basename(f), "right_diff=", round(d, 2))
    prev = right
