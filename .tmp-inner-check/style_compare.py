# -*- coding: utf-8 -*-
"""风格一致性：新旧特写帧 HSV 直方图相关性 + 色调分布对比。"""
import glob
import os

import cv2
import numpy as np

OLD_SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-login-check\shots"
NEW_SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
OLD_CLOSEUPS = ["home_000s.png", "home_001s.png", "home_002s.png", "home_005s.png", "home_006s.png",
                "home_007s.png", "home_011s.png", "home_012s.png", "home_014s.png", "home_018s.png",
                "home_020s.png", "home_026s.png", "home_028s.png", "home_034s.png", "home_040s.png",
                "home_042s.png", "home_062s.png"]
NEW_CLOSEUPS = ["frame_00.png", "frame_01.png", "frame_03.png", "frame_05.png", "frame_06.png",
                "frame_07.png", "frame_08.png", "frame_09.png", "frame_11.png", "frame_16.png",
                "frame_17.png", "frame_19.png", "frame_21.png", "frame_23.png", "frame_25.png",
                "frame_27.png"]


def hist_features(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    img = cv2.resize(img, (960, int(h * (960.0 / w))))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # 仅取右半场景区（避开左文案）
    roi = hsv[int(hsv.shape[0] * 0.06):int(hsv.shape[0] * 0.94), int(960 * 0.52):]
    hh = cv2.calcHist([roi], [0], None, [18], [0, 180])
    ss = cv2.calcHist([roi], [1], None, [16], [0, 256])
    vv = cv2.calcHist([roi], [2], None, [16], [0, 256])
    for a in (hh, ss, vv):
        s = a.sum()
        if s > 0:
            a /= s
    return np.concatenate([hh.flatten(), ss.flatten(), vv.flatten()])


old_feats = np.array([hist_features(os.path.join(OLD_SHOTS, f)) for f in OLD_CLOSEUPS])
new_feats = np.array([hist_features(os.path.join(NEW_SHOTS, f)) for f in NEW_CLOSEUPS])
old_mean = old_feats.mean(axis=0)
new_mean = new_feats.mean(axis=0)
corr = cv2.compareHist(old_mean.astype(np.float32), new_mean.astype(np.float32), cv2.HISTCMP_CORREL)
bhat = cv2.compareHist(old_mean.astype(np.float32), new_mean.astype(np.float32), cv2.HISTCMP_BHATTACHARYYA)
print(f"旧版特写帧数: {len(old_feats)}  新版特写帧数: {len(new_feats)}")
print(f"HSV 联合直方图相关性(旧mean vs 新mean): {corr:.4f}")
print(f"Bhattacharyya 距离: {bhat:.4f}")
# 亮度分布对比
old_v = np.array([hist_features(os.path.join(OLD_SHOTS, f))[18 + 16:] for f in OLD_CLOSEUPS]).mean(axis=0)
new_v = np.array([hist_features(os.path.join(NEW_SHOTS, f))[18 + 16:] for f in NEW_CLOSEUPS]).mean(axis=0)
print("亮度直方图(旧 mean):", [round(float(x), 3) for x in old_v])
print("亮度直方图(新 mean):", [round(float(x), 3) for x in new_v])
# 色调分布
old_h = np.array([hist_features(os.path.join(OLD_SHOTS, f))[:18] for f in OLD_CLOSEUPS]).mean(axis=0)
new_h = np.array([hist_features(os.path.join(NEW_SHOTS, f))[:18] for f in NEW_CLOSEUPS]).mean(axis=0)
print("色调直方图(旧 mean):", [round(float(x), 3) for x in old_h])
print("色调直方图(新 mean):", [round(float(x), 3) for x in new_h])
