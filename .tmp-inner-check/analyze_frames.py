# -*- coding: utf-8 -*-
"""特写帧像素级检查：近白占比 / 最大白色连通块 / 帧间差异 / Laplacian 方差。"""
import glob
import os

import numpy as np
from PIL import Image

SHOTS = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\shots"
frames = sorted(glob.glob(os.path.join(SHOTS, "frame_*.png")))
print("frames:", len(frames))

imgs = []
for f in frames:
    im = Image.open(f).convert("RGB").resize((960, 540))
    imgs.append(np.asarray(im, dtype=np.uint8))

prev = None
for idx, (f, a) in enumerate(zip(frames, imgs)):
    near_white = ((a[:, :, 0] >= 250) & (a[:, :, 1] >= 250) & (a[:, :, 2] >= 250))
    nw_ratio = near_white.mean()
    # 最大连通块（4 邻域，BFS 采样加速：先下采样掩码）
    mask = near_white[::4, ::4]
    max_cc = 0
    seen = np.zeros_like(mask, dtype=bool)
    from collections import deque
    H, W = mask.shape
    for y in range(H):
        for x in range(W):
            if mask[y, x] and not seen[y, x]:
                q = deque([(y, x)])
                seen[y, x] = True
                cnt = 0
                while q:
                    cy, cx = q.popleft()
                    cnt += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            q.append((ny, nx))
                max_cc = max(max_cc, cnt)
    # 掩码下采样 4x → 每像素代表 16 原像素
    cc_ratio = max_cc * 16 / (a.shape[0] * a.shape[1])
    # Laplacian 方差（灰度）
    g = np.asarray(Image.fromarray(a).convert("L"), dtype=np.float64)
    lap = np.abs(
        4 * g[1:-1, 1:-1]
        - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    )
    lap_var = lap.var()
    diff = 0.0
    if prev is not None:
        diff = float(np.abs(a.astype(np.int16) - prev.astype(np.int16)).mean())
    prev = a
    print(f"{os.path.basename(f)}: near_white={nw_ratio*100:.2f}% max_cc={cc_ratio*100:.3f}% lap_var={lap_var:.0f} frame_diff={diff:.1f}")
