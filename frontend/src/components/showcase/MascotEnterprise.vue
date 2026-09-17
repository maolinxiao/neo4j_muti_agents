<template>
  <svg viewBox="0 0 140 150" class="mascot-svg" aria-hidden="true">
    <!-- 企业研究员：白大褂 + 放大镜（简约几何扁平，金色调） -->
    <defs>
      <linearGradient id="mEntCoat" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#ffffff"/>
        <stop offset="1" stop-color="#e8eef6"/>
      </linearGradient>
    </defs>
    <!-- 头 -->
    <circle cx="66" cy="40" r="23" fill="#f6d7b8"/>
    <!-- 头发 -->
    <path d="M43 38 Q44 16 66 16 Q88 16 89 38 Q78 28 66 29 Q52 30 43 38 Z" fill="#3f4756"/>
    <!-- 眼睛与微笑 -->
    <circle cx="59" cy="42" r="2.4" fill="#2d3436"/>
    <circle cx="74" cy="42" r="2.4" fill="#2d3436"/>
    <path d="M61 51 Q66.5 55 72 51" fill="none" stroke="#2d3436" stroke-width="2" stroke-linecap="round"/>
    <!-- 白大褂身体 -->
    <path d="M40 134 L40 86 Q40 66 58 63 L74 63 Q92 66 92 86 L92 134 Z" fill="url(#mEntCoat)" stroke="#dbe4ee" stroke-width="1.5"/>
    <!-- 衬衫领口与领带 -->
    <path d="M58 63 L66 76 L74 63" fill="none" stroke="#cbd5e1" stroke-width="2"/>
    <path d="M66 76 L69 92 L66 104 L63 92 Z" fill="#d97706"/>
    <!-- 大褂扣 -->
    <circle cx="80" cy="96" r="2" fill="#cbd5e1"/>
    <circle cx="80" cy="108" r="2" fill="#cbd5e1"/>
    <!-- 手持放大镜 -->
    <circle cx="112" cy="94" r="13" fill="rgba(217,119,6,0.1)" stroke="#d97706" stroke-width="4"/>
    <line x1="103" y1="104" x2="94" y2="116" stroke="#b45309" stroke-width="5" stroke-linecap="round"/>
    <circle cx="108" cy="90" r="4" fill="rgba(255,255,255,0.85)"/>
    <!-- 手臂连接 -->
    <path d="M40 92 Q30 100 32 112" fill="none" stroke="#e8eef6" stroke-width="9" stroke-linecap="round"/>
    <path d="M92 92 Q100 94 100 100" fill="none" stroke="#e8eef6" stroke-width="9" stroke-linecap="round"/>
  </svg>
</template>
