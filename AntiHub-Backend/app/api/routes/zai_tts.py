"""
ZAI TTS 账号管理 API
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.zai_tts import (
    ZaiTTSAccountCreateRequest,
    ZaiTTSAccountUpdateStatusRequest,
    ZaiTTSAccountUpdateNameRequest,
    ZaiTTSAccountUpdateCredentialsRequest,
    ZaiTTSAccountResponse,
)
from app.services.zai_tts_service import ZaiTTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zai-tts", tags=["ZAI TTS账号管理"])


def get_zai_tts_service(db: AsyncSession = Depends(get_db_session)) -> ZaiTTSService:
    return ZaiTTSService(db)


def _serialize(account) -> dict:
    return ZaiTTSAccountResponse.model_validate(account).model_dump(by_alias=False)


@router.post("/accounts", summary="创建 ZAI TTS 账号")
async def create_zai_tts_account(
    request: ZaiTTSAccountCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    try:
        account = await service.create_account(
            current_user.id,
            account_name=request.account_name,
            zai_user_id=request.zai_user_id,
            token=request.token,
            voice_id=request.voice_id,
        )
        return {"success": True, "data": _serialize(account)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("create zai tts account failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建账号失败",
        )


@router.get("/accounts", summary="获取 ZAI TTS 账号列表")
async def list_zai_tts_accounts(
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    try:
        accounts = await service.list_accounts(current_user.id)
        return {"success": True, "data": [_serialize(a) for a in accounts]}
    except Exception as e:
        logger.error("list zai tts accounts failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取账号列表失败",
        )


@router.get("/accounts/{account_id}", summary="获取 ZAI TTS 账号详情")
async def get_zai_tts_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    account = await service.repo.get_by_id_and_user_id(account_id, current_user.id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"success": True, "data": _serialize(account)}


@router.put("/accounts/{account_id}/status", summary="更新 ZAI TTS 账号状态")
async def update_zai_tts_account_status(
    account_id: int,
    request: ZaiTTSAccountUpdateStatusRequest,
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    if request.status not in (0, 1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status 必须是 0 或 1")
    account = await service.update_status(current_user.id, account_id, request.status)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"success": True, "data": _serialize(account)}


@router.put("/accounts/{account_id}/name", summary="更新 ZAI TTS 账号名称")
async def update_zai_tts_account_name(
    account_id: int,
    request: ZaiTTSAccountUpdateNameRequest,
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    account_name = request.account_name.strip()
    if not account_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="账号名称不能为空")
    account = await service.update_name(current_user.id, account_id, account_name)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"success": True, "data": _serialize(account)}


@router.put("/accounts/{account_id}/credentials", summary="更新 ZAI TTS 账号配置")
async def update_zai_tts_account_credentials(
    account_id: int,
    request: ZaiTTSAccountUpdateCredentialsRequest,
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    if request.zai_user_id is not None and not request.zai_user_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="zai_user_id 不能为空")
    if request.voice_id is not None and not request.voice_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="voice_id 不能为空")
    account = await service.update_credentials(
        current_user.id,
        account_id,
        zai_user_id=request.zai_user_id,
        token=request.token,
        voice_id=request.voice_id,
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"success": True, "data": _serialize(account)}


@router.delete("/accounts/{account_id}", summary="删除 ZAI TTS 账号")
async def delete_zai_tts_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    service: ZaiTTSService = Depends(get_zai_tts_service),
):
    ok = await service.delete_account(current_user.id, account_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"success": True}
