"""
ZAI TTS 账号数据仓储

约定：
- Repository 层不负责 commit()，事务由调用方统一管理
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zai_tts_account import ZaiTTSAccount


class ZaiTTSAccountRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user_id(self, user_id: int) -> Sequence[ZaiTTSAccount]:
        result = await self.db.execute(
            select(ZaiTTSAccount)
            .where(ZaiTTSAccount.user_id == user_id)
            .order_by(ZaiTTSAccount.id.asc())
        )
        return result.scalars().all()

    async def list_enabled_by_user_id(self, user_id: int) -> Sequence[ZaiTTSAccount]:
        result = await self.db.execute(
            select(ZaiTTSAccount)
            .where(ZaiTTSAccount.user_id == user_id, ZaiTTSAccount.status == 1)
            .order_by(ZaiTTSAccount.id.asc())
        )
        return result.scalars().all()

    async def get_by_id_and_user_id(self, account_id: int, user_id: int) -> Optional[ZaiTTSAccount]:
        result = await self.db.execute(
            select(ZaiTTSAccount).where(
                ZaiTTSAccount.id == account_id,
                ZaiTTSAccount.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        account_name: str,
        zai_user_id: str,
        voice_id: str,
        credentials: str,
        status: int = 1,
    ) -> ZaiTTSAccount:
        account = ZaiTTSAccount(
            user_id=user_id,
            account_name=account_name,
            status=status,
            zai_user_id=zai_user_id,
            voice_id=voice_id,
            credentials=credentials,
        )
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def update_status(self, account_id: int, user_id: int, status: int) -> Optional[ZaiTTSAccount]:
        await self.db.execute(
            update(ZaiTTSAccount)
            .where(
                ZaiTTSAccount.id == account_id,
                ZaiTTSAccount.user_id == user_id,
            )
            .values(status=status)
        )
        await self.db.flush()
        return await self.get_by_id_and_user_id(account_id, user_id)

    async def update_name(self, account_id: int, user_id: int, account_name: str) -> Optional[ZaiTTSAccount]:
        await self.db.execute(
            update(ZaiTTSAccount)
            .where(
                ZaiTTSAccount.id == account_id,
                ZaiTTSAccount.user_id == user_id,
            )
            .values(account_name=account_name)
        )
        await self.db.flush()
        return await self.get_by_id_and_user_id(account_id, user_id)

    async def update_credentials(
        self,
        account_id: int,
        user_id: int,
        *,
        zai_user_id: Optional[str] = None,
        voice_id: Optional[str] = None,
        credentials: Optional[str] = None,
    ) -> Optional[ZaiTTSAccount]:
        values = {}
        if zai_user_id is not None:
            values["zai_user_id"] = zai_user_id
        if voice_id is not None:
            values["voice_id"] = voice_id
        if credentials is not None:
            values["credentials"] = credentials

        if not values:
            return await self.get_by_id_and_user_id(account_id, user_id)

        await self.db.execute(
            update(ZaiTTSAccount)
            .where(
                ZaiTTSAccount.id == account_id,
                ZaiTTSAccount.user_id == user_id,
            )
            .values(**values)
        )
        await self.db.flush()
        return await self.get_by_id_and_user_id(account_id, user_id)

    async def delete(self, account_id: int, user_id: int) -> bool:
        result = await self.db.execute(
            delete(ZaiTTSAccount).where(
                ZaiTTSAccount.id == account_id,
                ZaiTTSAccount.user_id == user_id,
            )
        )
        await self.db.flush()
        return (result.rowcount or 0) > 0

    async def update_last_used_at(self, account_id: int, user_id: int) -> None:
        await self.db.execute(
            update(ZaiTTSAccount)
            .where(
                ZaiTTSAccount.id == account_id,
                ZaiTTSAccount.user_id == user_id,
            )
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self.db.flush()
