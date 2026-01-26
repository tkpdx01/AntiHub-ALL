"""
ZAI TTS 账号数据模型

说明：
- 账号归属到 User（user_id），支持同一用户保存多个 ZAI TTS 账号
- token 使用加密后的 JSON 字符串存储，避免明文落库
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ZaiTTSAccount(Base):
    """ZAI TTS 账号模型"""

    __tablename__ = "zai_tts_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联的用户ID",
    )

    account_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="账号显示名称",
    )

    status: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="账号状态：0=禁用，1=启用",
    )

    zai_user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="ZAI 用户ID",
    )

    voice_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="默认音色ID",
    )

    credentials: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="加密后的凭证 JSON（含 token）",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后使用时间",
    )

    user: Mapped["User"] = relationship("User", back_populates="zai_tts_accounts")

    def __repr__(self) -> str:
        return f"<ZaiTTSAccount(id={self.id}, user_id={self.user_id}, zai_user_id='{self.zai_user_id}')>"
