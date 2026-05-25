import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

const herbs = [
  { x: 270, y: 250, label: "黄芪", delay: 0 },
  { x: 520, y: 180, label: "人参", delay: 18 },
  { x: 760, y: 350, label: "枸杞", delay: 34 },
  { x: 1060, y: 250, label: "山药", delay: 50 },
  { x: 1290, y: 430, label: "蜂蜜", delay: 66 },
  { x: 940, y: 650, label: "体质", delay: 82 },
  { x: 600, y: 700, label: "消费者", delay: 98 },
];

const connections = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [2, 5],
  [5, 6],
  [6, 0],
];

const pulse = (frame, delay) => {
  const local = (frame - delay + 180) % 180;
  return interpolate(local, [0, 45, 90, 180], [0.35, 1, 0.5, 0.35]);
};

export const LoginBackground = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const drift = Math.sin(frame / 34) * 18;
  const sweep = interpolate(frame % 180, [0, 180], [-260, width + 260]);

  return (
    <AbsoluteFill
      style={{
        background:
          "linear-gradient(135deg, #102238 0%, #174256 48%, #111827 100%)",
        overflow: "hidden",
        fontFamily: "Microsoft YaHei, PingFang SC, Arial, sans-serif",
      }}
    >
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <radialGradient id="glowA" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#78d8b7" stopOpacity="0.34" />
            <stop offset="100%" stopColor="#78d8b7" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="glowB" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#69b7ff" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#69b7ff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="line" x1="0%" x2="100%" y1="0%" y2="0%">
            <stop offset="0%" stopColor="#78d8b7" stopOpacity="0.08" />
            <stop offset="50%" stopColor="#9ad4ff" stopOpacity="0.38" />
            <stop offset="100%" stopColor="#78d8b7" stopOpacity="0.08" />
          </linearGradient>
        </defs>

        <rect width={width} height={height} fill="rgba(5,12,24,0.18)" />
        <circle cx={360 + drift} cy={270} r={360} fill="url(#glowA)" />
        <circle cx={1120 - drift} cy={620} r={430} fill="url(#glowB)" />
        <circle cx={sweep} cy={height * 0.48} r={220} fill="rgba(255,255,255,0.045)" />

        {[180, 290, 420].map((radius, index) => (
          <circle
            key={radius}
            cx={width * 0.26}
            cy={height * 0.34}
            r={radius + Math.sin(frame / 26 + index) * 8}
            fill="none"
            stroke="#8cc8ff"
            strokeOpacity={0.11}
            strokeWidth="2"
          />
        ))}

        {[240, 380, 520].map((radius, index) => (
          <circle
            key={radius}
            cx={width * 0.68}
            cy={height * 0.62}
            r={radius + Math.cos(frame / 30 + index) * 10}
            fill="none"
            stroke="#78d8b7"
            strokeOpacity={0.1}
            strokeWidth="2"
          />
        ))}

        {connections.map(([from, to]) => {
          const a = herbs[from];
          const b = herbs[to];
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x}
              y1={a.y + Math.sin(frame / 40 + from) * 12}
              x2={b.x}
              y2={b.y + Math.sin(frame / 40 + to) * 12}
              stroke="url(#line)"
              strokeWidth="3"
            />
          );
        })}

        {herbs.map((node, index) => {
          const opacity = pulse(frame, node.delay);
          const y = node.y + Math.sin(frame / 36 + index) * 14;
          return (
            <g key={node.label} transform={`translate(${node.x} ${y})`}>
              <circle r={34} fill="#0f766e" opacity={0.22 + opacity * 0.24} />
              <circle r={18} fill="#c9f7df" opacity={0.45 + opacity * 0.35} />
              <text
                x="0"
                y="58"
                textAnchor="middle"
                fill="#f8fafc"
                opacity={0.62 + opacity * 0.28}
                fontSize="24"
                fontWeight="600"
              >
                {node.label}
              </text>
            </g>
          );
        })}

        <path
          d={`M120 ${760 + drift * 0.4} C 360 650, 580 850, 880 720 S 1260 540, 1620 720`}
          fill="none"
          stroke="#f8fafc"
          strokeOpacity="0.12"
          strokeWidth="2"
        />
        <path
          d={`M90 ${330 - drift * 0.3} C 330 200, 560 440, 860 310 S 1240 140, 1580 320`}
          fill="none"
          stroke="#78d8b7"
          strokeOpacity="0.16"
          strokeWidth="2"
        />
      </svg>
    </AbsoluteFill>
  );
};
