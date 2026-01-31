"""
Spec 白名单校验入口（统一 403 文案）。

用途：各 Spec 路由在入口处调用，避免在每个路由里散落 hardcode + 重复 raise。
"""

from __future__ import annotations

from typing import Optional
import logging

from fastapi import HTTPException, status

from app.core.spec_allowlist import DEFAULT_SPEC_CONFIG_TYPE_ALLOWLIST, SpecName

logger = logging.getLogger(__name__)

SPEC_NOT_SUPPORTED_DETAIL = "不支持的规范"


def ensure_spec_allowed(spec: SpecName, config_type: Optional[str]) -> None:
    """
    规范级白名单校验（默认使用“现状 allowlist”）。

    - 允许：不改变业务路径（直接返回）
    - 拒绝：统一抛 403 + detail=不支持的规范
    """

    normalized_type = (config_type or "").strip().lower()
    allowed = DEFAULT_SPEC_CONFIG_TYPE_ALLOWLIST.get(spec)

    if not allowed or normalized_type not in allowed:
        # 注意：不要记录原始 API key；这里只记录 spec/config_type 用于定位。
        logger.info(
            "spec rejected by allowlist: spec=%s config_type=%s",
            spec,
            normalized_type or None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SPEC_NOT_SUPPORTED_DETAIL,
        )

