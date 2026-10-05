// 会话时间显示：列表用相对时间（紧凑），悬停 tooltip 给完整时间。

const pad = (n) => String(n).padStart(2, "0");

export const formatDateTime = (value) => {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value || "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export const formatRelativeTime = (value, locale = "zh-CN") => {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value || "";
  const diff = Date.now() - d.getTime();
  const minute = 60_000;
  const hour = 3_600_000;
  const day = 86_400_000;
  const en = locale === "en-US";
  if (diff < minute) return en ? "just now" : "刚刚";
  if (diff < hour) {
    const n = Math.floor(diff / minute);
    return en ? `${n} min ago` : `${n} 分钟前`;
  }
  if (diff < day) {
    const n = Math.floor(diff / hour);
    return en ? `${n} h ago` : `${n} 小时前`;
  }
  if (diff < 7 * day) {
    const n = Math.floor(diff / day);
    return en ? `${n} d ago` : `${n} 天前`;
  }
  return formatDateTime(value);
};
