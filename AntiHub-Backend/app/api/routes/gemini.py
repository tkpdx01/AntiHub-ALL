"""
Gemini兼容的API端点
支持Gemini API格式的图片生成 (/v1beta/models/{model}:generateContent)
支持图生图功能和SSE流式响应（每20秒心跳保活）
"""
from typing import Optional
import json
import logging
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_flexible import get_user_flexible_with_goog_api_key
from app.api.deps import get_db_session, get_plugin_api_service, get_redis
from app.cache import RedisClient
from app.models.user import User
from app.services.gemini_cli_api_service import GeminiCLIAPIService
from app.services.plugin_api_service import PluginAPIService
from app.schemas.plugin_api import GenerateContentRequest
from app.services.usage_log_service import UsageLogService, SSEUsageTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1beta", tags=["Gemini兼容API"])

class GeminiSSEUsageTracker:
    def __init__(self) -> None:
        self.buffer = ""
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.success = True
        self.status_code: Optional[int] = None
        self.error_message: Optional[str] = None
        self._seen_usage = False

    def feed(self, chunk: bytes) -> None:
        try:
            self.buffer += chunk.decode("utf-8", errors="replace")
        except Exception:
            return

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue

            data_str = line[5:].strip()
            if not data_str:
                continue

            try:
                payload = json.loads(data_str)
            except Exception:
                continue

            if not isinstance(payload, dict):
                continue

            # error: {"error": {"message": "...", "code": 429}}
            err = payload.get("error")
            if err is not None:
                self.success = False
                if isinstance(err, dict):
                    self.error_message = str(err.get("message") or err.get("detail") or err)
                    try:
                        self.status_code = int(err.get("code") or err.get("status") or 500)
                    except Exception:
                        self.status_code = self.status_code or 500
                else:
                    self.error_message = str(err)
                    self.status_code = self.status_code or 500

            usage = payload.get("usageMetadata")
            if isinstance(usage, dict):
                prompt = int(usage.get("promptTokenCount") or 0)
                thoughts = int(usage.get("thoughtsTokenCount") or 0)
                completion = int(usage.get("candidatesTokenCount") or 0)
                total = int(usage.get("totalTokenCount") or (prompt + completion))
                self.input_tokens = prompt + thoughts
                self.output_tokens = completion
                self.total_tokens = total
                self._seen_usage = True

    def finalize(self) -> None:
        if not self._seen_usage and self.total_tokens == 0:
            self.total_tokens = int(self.input_tokens) + int(self.output_tokens)


def get_gemini_cli_api_service(
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> GeminiCLIAPIService:
    return GeminiCLIAPIService(db, redis)


@router.post(
    "/models/{model}:generateContent",
    summary="图片生成",
    description="使用Gemini模型生成图片，支持文生图和图生图。支持JWT token、Bearer API key或x-goog-api-key标头认证。响应使用SSE格式（心跳保活）"
)
async def generate_content(
    model: str,
    request: GenerateContentRequest,
    raw_request: Request,
    current_user: User = Depends(get_user_flexible_with_goog_api_key),
    service: PluginAPIService = Depends(get_plugin_api_service),
    gemini_cli_service: GeminiCLIAPIService = Depends(get_gemini_cli_api_service),
):
    start_time = time.monotonic()
    endpoint = raw_request.url.path
    method = raw_request.method
    api_key_id = getattr(current_user, "_api_key_id", None)

    # 获取 config_type（通过 API key 认证时会设置）
    config_type = getattr(current_user, "_config_type", None)
    effective_config_type = config_type or "antigravity"

    try:
        # 获取 config_type（通过 API key 认证时会设置）
        if config_type == "gemini-cli":
            result = await gemini_cli_service.gemini_generate_content(
                user_id=current_user.id,
                model=model,
                request_data=request.model_dump(),
            )

            usage = result.get("usageMetadata") if isinstance(result, dict) else None
            if isinstance(usage, dict):
                in_tok = int(usage.get("promptTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0)
                out_tok = int(usage.get("candidatesTokenCount") or 0)
                total_tok = int(usage.get("totalTokenCount") or (in_tok + out_tok))
            else:
                in_tok, out_tok, total_tok = 0, 0, 0

            duration_ms = int((time.monotonic() - start_time) * 1000)
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=False,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=total_tok,
                success=True,
                status_code=200,
                duration_ms=duration_ms,
            )

            return result
        
        # 使用流式请求以支持SSE心跳保活
        tracker = SSEUsageTracker()

        async def generate():
            try:
                async for chunk in service.generate_content_stream(
                    user_id=current_user.id,
                    model=model,
                    request_data=request.model_dump(),
                    config_type=config_type,
                ):
                    if isinstance(chunk, (bytes, bytearray)):
                        tracker.feed(bytes(chunk))
                    else:
                        tracker.feed(str(chunk).encode("utf-8", errors="replace"))
                    yield chunk
            except Exception as e:
                tracker.success = False
                tracker.status_code = tracker.status_code or 500
                tracker.error_message = str(e)
                raise
            finally:
                tracker.finalize()
                duration_ms = int((time.monotonic() - start_time) * 1000)
                await UsageLogService.record(
                    user_id=current_user.id,
                    api_key_id=api_key_id,
                    endpoint=endpoint,
                    method=method,
                    model_name=model,
                    config_type=effective_config_type,
                    stream=True,
                    input_tokens=tracker.input_tokens,
                    output_tokens=tracker.output_tokens,
                    total_tokens=tracker.total_tokens,
                    success=tracker.success,
                    status_code=tracker.status_code,
                    error_message=tracker.error_message,
                    duration_ms=duration_ms,
                )
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except httpx.HTTPStatusError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        # 透传上游API的错误响应
        error_data = getattr(e, 'response_data', {"detail": str(e)})
        if isinstance(error_data, dict) and 'detail' in error_data:
            detail = error_data['detail']
        else:
            detail = error_data

        if effective_config_type == "gemini-cli":
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=False,
                success=False,
                status_code=e.response.status_code if e.response is not None else None,
                error_message=str(detail),
                duration_ms=duration_ms,
            )

        raise HTTPException(
            status_code=e.response.status_code,
            detail=detail
        )
    except ValueError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        if effective_config_type == "gemini-cli":
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=False,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        if effective_config_type == "gemini-cli":
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=False,
                success=False,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        logger.error(f"图片生成失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图片生成失败: {str(e)}"
        )

@router.post(
    "/models/{model}:streamGenerateContent",
    summary="图片生成（流式）",
    description="使用Gemini模型生成图片，支持文生图和图生图。支持JWT token、Bearer API key或x-goog-api-key标头认证。响应使用SSE格式（心跳保活）。使用 ?alt=sse 查询参数启用SSE流式响应。"
)
async def stream_generate_content(
    model: str,
    request: GenerateContentRequest,
    raw_request: Request,
    alt: str = Query(default="sse", description="响应格式，默认为sse"),
    current_user: User = Depends(get_user_flexible_with_goog_api_key),
    service: PluginAPIService = Depends(get_plugin_api_service),
    gemini_cli_service: GeminiCLIAPIService = Depends(get_gemini_cli_api_service),
):
    start_time = time.monotonic()
    endpoint = raw_request.url.path
    method = raw_request.method
    api_key_id = getattr(current_user, "_api_key_id", None)

    config_type = getattr(current_user, "_config_type", None)
    effective_config_type = config_type or "antigravity"

    try:
        # 获取 config_type（通过 API key 认证时会设置）
        if config_type == "gemini-cli":
            if alt != "sse":
                raise ValueError("GeminiCLI 目前仅支持 alt=sse 的流式响应")

            tracker = GeminiSSEUsageTracker()

            async def generate():
                try:
                    async for chunk in gemini_cli_service.gemini_stream_generate_content(
                        user_id=current_user.id,
                        model=model,
                        request_data=request.model_dump(),
                    ):
                        tracker.feed(chunk)
                        yield chunk
                except Exception as e:
                    tracker.success = False
                    tracker.status_code = tracker.status_code or 500
                    tracker.error_message = str(e)
                    raise
                finally:
                    tracker.finalize()
                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    await UsageLogService.record(
                        user_id=current_user.id,
                        api_key_id=api_key_id,
                        endpoint=endpoint,
                        method=method,
                        model_name=model,
                        config_type=effective_config_type,
                        stream=True,
                        input_tokens=tracker.input_tokens,
                        output_tokens=tracker.output_tokens,
                        total_tokens=tracker.total_tokens,
                        success=tracker.success,
                        status_code=tracker.status_code,
                        error_message=tracker.error_message,
                        duration_ms=duration_ms,
                    )

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        
        # 使用流式请求以支持SSE心跳保活
        tracker = SSEUsageTracker()

        async def generate():
            try:
                async for chunk in service.generate_content_stream(
                    user_id=current_user.id,
                    model=model,
                    request_data=request.model_dump(),
                    config_type=config_type,
                ):
                    if isinstance(chunk, (bytes, bytearray)):
                        tracker.feed(bytes(chunk))
                    else:
                        tracker.feed(str(chunk).encode("utf-8", errors="replace"))
                    yield chunk
            except Exception as e:
                tracker.success = False
                tracker.status_code = tracker.status_code or 500
                tracker.error_message = str(e)
                raise
            finally:
                tracker.finalize()
                duration_ms = int((time.monotonic() - start_time) * 1000)
                await UsageLogService.record(
                    user_id=current_user.id,
                    api_key_id=api_key_id,
                    endpoint=endpoint,
                    method=method,
                    model_name=model,
                    config_type=effective_config_type,
                    stream=True,
                    input_tokens=tracker.input_tokens,
                    output_tokens=tracker.output_tokens,
                    total_tokens=tracker.total_tokens,
                    success=tracker.success,
                    status_code=tracker.status_code,
                    error_message=tracker.error_message,
                    duration_ms=duration_ms,
                )
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except httpx.HTTPStatusError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        # 透传上游API的错误响应
        error_data = getattr(e, 'response_data', {"detail": str(e)})
        if isinstance(error_data, dict) and 'detail' in error_data:
            detail = error_data['detail']
        else:
            detail = error_data

        if effective_config_type == "gemini-cli":
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=True,
                success=False,
                status_code=e.response.status_code if e.response is not None else None,
                error_message=str(detail),
                duration_ms=duration_ms,
            )

        raise HTTPException(
            status_code=e.response.status_code,
            detail=detail
        )
    except ValueError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        if effective_config_type == "gemini-cli":
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=True,
                success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        if effective_config_type == "gemini-cli":
            await UsageLogService.record(
                user_id=current_user.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                method=method,
                model_name=model,
                config_type=effective_config_type,
                stream=True,
                success=False,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        logger.error(f"图片生成失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图片生成失败: {str(e)}"
        )
