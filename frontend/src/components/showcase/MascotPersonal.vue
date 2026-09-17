<template>
  <svg viewBox="0 0 140 150" class="mascot-svg" aria-hidden="true">
    <!-- 养生人：捧茶杯 + 头顶叶芽（简约几何扁平，绿色调） -->
    <defs>
      <linearGradient id="mPerSweater" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#34d399"/>
        <stop offset="1" stop-color="#059669"/>
      </linearGradient>
    </defs>
    <!-- 头 -->
    <circle cx="70" cy="42" r="23" fill="#f6d7b8"/>
    <!-- 头发 -->
    <path d="M47 40 Q48 18 70 18 Q92 18 93 40 Q82 30 70 31 Q56 32 47 40 Z" fill="#4a3f35"/>
    <!-- 头顶叶芽 -->
    <path d="M70 16 Q70 6 80 4 Q80 14 70 16 Z" fill="#34d399"/>
    <path d="M70 16 Q70 8 61 6 Q61 15 70 16 Z" fill="#10b981"/>
    <!-- 眼睛与微笑 -->
    <circle cx="63" cy="44" r="2.4" fill="#2d3436"/>
    <circle cx="78" cy="44" r="2.4" fill="#2d3436"/>
    <path d="M65 53 Q70.5 57 76 53" fill="none" stroke="#2d3436" stroke-width="2" stroke-linecap="round"/>
    <!-- 腮红 -->
    <circle cx="56" cy="50" r="3.4" fill="#f9b98a" opacity="0.7"/>
    <circle cx="85" cy="50" r="3.4" fill="#f9b98a" opacity="0.7"/>
    <!-- 毛衣身体 -->
    <path d="M42 134 L42 88 Q42 68 60 65 L80 65 Q98 68 98 88 L98 134 Z" fill="url(#mPerSweater)"/>
    <!-- 双手捧杯 -->
    <path d="M46 96 Q42 108 50 116" fill="none" stroke="#2ea87a" stroke-width="9" stroke-linecap="round"/>
    <path d="M94 96 Q98 108 90 116" fill="none" stroke="#2ea87a" stroke-width="9" stroke-linecap="round"/>
    <!-- 茶杯 -->
    <path d="M56 108 L84 108 L81 126 L59 126 Z" fill="#f0fdf4" stroke="#d1fae5" stroke-width="1.5"/>
    <ellipse cx="70" cy="108" rx="14" ry="3.6" fill="#d1fae5"/>
    <path d="M62 102 Q64 97 62 93" fill="none" stroke="#a7f3d0" stroke-width="2" stroke-linecap="round"/>
    <path d="M72 102 Q74 96 72 91" fill="none" stroke="#a7f3d0" stroke-width="2" stroke-linecap="round"/>
    <!-- 衣领 -->
    <path d="M60 65 L70 74 L80 65" fill="none" stroke="#d1fae5" stroke-width="2"/>
  </svg>
</template>
