"""图形验证码服务（CaptchaStore，内存实现）。

说明：
- 本实现为进程内 dict + 线程锁，适用于**单 worker 部署**（uvicorn 单进程 / --workers 1）。
- 若部署为多 worker/多实例，需升级为 DB 存储：ORM 模型 `CaptchaCode`（app.db.models）已定义，
  将 `CaptchaStore` 替换为基于该表的实现即可（接口 issue/verify 不变）。
- 只存储验证码文本的 sha256 摘要（code_hash），内存中不保存明文。
- 不引入其它运行时依赖（Pillow 详见根目录 requirements.txt）。
"""

import base64
import hashlib
import io
import logging
import random
import secrets
import threading
import time
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

logger = logging.getLogger(__name__)

# 去除易混淆字符 0/O/o、1/l/I
CAPTCHA_CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
_IMAGE_WIDTH = 120
_IMAGE_HEIGHT = 40

# verify() 返回值：可区分的失败原因（路由层据此返回对应提示文案）
CAPTCHA_OK = "ok"  # 校验通过（一次性作废）
CAPTCHA_INVALID = "invalid"  # id/文本为空，或记录不存在（含已作废后再次提交）
CAPTCHA_EXPIRED = "expired"  # 超过 TTL
CAPTCHA_IP_MISMATCH = "ip_mismatch"  # 提交 IP 与签发 IP 不一致
CAPTCHA_USED = "used"  # 已成功校验过（一次性作废后再提交）
CAPTCHA_ATTEMPTS_EXCEEDED = "attempts_exceeded"  # 错误尝试达到上限
CAPTCHA_TEXT_MISMATCH = "text_mismatch"  # 文本不匹配（记录仍有效，可重试）


@dataclass
class _CaptchaRecord:
    code_hash: str
    expires_at: float
    attempts: int = 0
    used: bool = False
    ip: str = ""


class CaptchaStore:
    """内存验证码存储：issue(ip) -> (captcha_id, image_base64)；verify(id, text, ip) -> 结果原因（CAPTCHA_OK 或失败原因常量）。"""

    def __init__(self) -> None:
        self._records: dict[str, _CaptchaRecord] = {}
        self._lock = threading.Lock()

    def issue(self, ip: str = "") -> tuple[str, str]:
        """签发一张验证码，返回 (captcha_id, base64 编码的 PNG)。"""
        self._cleanup()
        text = "".join(secrets.choice(CAPTCHA_CHARSET) for _ in range(max(1, settings.captcha_length)))
        record = _CaptchaRecord(
            code_hash=self._hash(self._normalize(text)),
            expires_at=time.time() + settings.captcha_ttl_seconds,
            ip=ip or "",
        )
        captcha_id = secrets.token_hex(16)
        with self._lock:
            self._records[captcha_id] = record
        return captcha_id, self._render_base64(text)

    def verify(self, captcha_id: str, text: str, ip: str = "") -> str:
        """校验验证码，返回 CAPTCHA_OK 或具体失败原因（见模块常量）。

        规则：TTL 过期 / 已使用 / 尝试次数达到 captcha_fail_max / IP 不一致（签发时有 IP 且当前不同）
        均判定失败并返回可区分原因；成功即作废（一次性），失败累计 attempts，达到上限即作废。
        文本比较不区分大小写且忽略首尾空白（issue 侧按同一规则归一化存储摘要）。
        """
        if not captcha_id or not text or not text.strip():
            return CAPTCHA_INVALID
        now = time.time()
        with self._lock:
            record = self._records.get(captcha_id)
            if record is None:
                reason = CAPTCHA_INVALID
            elif now >= record.expires_at:
                self._records.pop(captcha_id, None)
                reason = CAPTCHA_EXPIRED
            elif record.ip and ip and record.ip != ip:
                reason = CAPTCHA_IP_MISMATCH
            elif record.used:
                reason = CAPTCHA_USED
            elif record.attempts >= settings.captcha_fail_max:
                reason = CAPTCHA_ATTEMPTS_EXCEEDED
            else:
                record.attempts += 1
                if secrets.compare_digest(record.code_hash, self._hash(self._normalize(text))):
                    record.used = True
                    reason = CAPTCHA_OK
                else:
                    reason = (
                        CAPTCHA_ATTEMPTS_EXCEEDED
                        if record.attempts >= settings.captcha_fail_max
                        else CAPTCHA_TEXT_MISMATCH
                    )
        if reason != CAPTCHA_OK:
            logger.warning(
                "captcha verify failed: reason=%s ip=%s captcha_id=%s attempts=%s",
                reason,
                ip or "-",
                (captcha_id[:8] + "..") if captcha_id else "-",
                record.attempts if record is not None else "-",
            )
        return reason

    def _cleanup(self) -> None:
        """清理过期/已使用的记录。"""
        now = time.time()
        with self._lock:
            expired = [cid for cid, r in self._records.items() if now >= r.expires_at or r.used]
            for cid in expired:
                self._records.pop(cid, None)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize(text: str) -> str:
        """归一化比较文本：去首尾空白并转大写（字符集内大小写等价），实现不区分大小写比较。"""
        return (text or "").strip().upper()

    @staticmethod
    def _render_base64(text: str) -> str:
        """用 Pillow 绘制 120x40 PNG（噪点 + 干扰线），返回 base64 字符串。"""
        image = Image.new("RGB", (_IMAGE_WIDTH, _IMAGE_HEIGHT), (245, 247, 250))
        draw = ImageDraw.Draw(image)
        font = CaptchaStore._load_font()
        # 每个字符独立随机颜色
        for index, char in enumerate(text):
            x = 12 + index * ((_IMAGE_WIDTH - 24) // max(1, len(text)))
            y = 6 + random.randint(-2, 6)
            color = (random.randint(20, 90), random.randint(20, 90), random.randint(20, 90))
            draw.text((x, y), char, font=font, fill=color)
        # 噪点
        for _ in range(60):
            x = random.randint(0, _IMAGE_WIDTH - 1)
            y = random.randint(0, _IMAGE_HEIGHT - 1)
            draw.point((x, y), fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)))
        # 干扰线
        for _ in range(3):
            x1 = random.randint(0, _IMAGE_WIDTH)
            y1 = random.randint(0, _IMAGE_HEIGHT)
            x2 = random.randint(0, _IMAGE_WIDTH)
            y2 = random.randint(0, _IMAGE_HEIGHT)
            draw.line((x1, y1, x2, y2), fill=(random.randint(120, 200), random.randint(120, 200), random.randint(120, 200)), width=1)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    @staticmethod
    def _load_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
        for name in ("arial.ttf", "DejaVuSans.ttf", "msyh.ttc", "simhei.ttf"):
            try:
                return ImageFont.truetype(name, 28)
            except OSError:
                continue
        return ImageFont.load_default()
