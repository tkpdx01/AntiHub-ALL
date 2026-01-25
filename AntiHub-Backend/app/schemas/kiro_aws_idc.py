"""
Kiro AWS IdC / Builder ID 相关的请求模型

注意：
- 这里的“IdC / Builder ID”指 AWS IAM Identity Center（SSO OIDC）设备码登录链路。
- 本模块刻意与现有的 Kiro OAuth（Google/Github）以及 Kiro Token 导入分离，避免语义混用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KiroAwsIdcImportRequest(BaseModel):
    """
    方案 A：手动导入本地凭据（token.json + client.json）

    前端读取文件内容后，直接把 JSON 结构提交到后端即可（不建议把“文件上传/解析”做到后端）。
    """

    json_files: List[Dict[str, Any]] = Field(
        ...,
        description="从本地读取到的 JSON 内容列表（通常包含 token.json 与 client.json 两份）",
    )
    account_name: Optional[str] = Field(
        None, description="账号显示名称（可选，不传则后端使用默认值）"
    )
    region: Optional[str] = Field(
        None, description="AWS 区域ID（例如 us-east-1），不传则默认 us-east-1"
    )
    is_shared: int = Field(0, description="0=私有账号，1=共享账号")


class KiroAwsIdcDeviceAuthorizeRequest(BaseModel):
    """
    方案 B：Builder ID 设备码登录（Device Authorization Flow）
    """

    account_name: Optional[str] = Field(
        None, description="账号显示名称（可选，不传则后端使用默认值）"
    )
    region: Optional[str] = Field(
        None, description="AWS 区域ID（例如 us-east-1），不传则默认 us-east-1"
    )
    is_shared: int = Field(0, description="0=私有账号，1=共享账号")
