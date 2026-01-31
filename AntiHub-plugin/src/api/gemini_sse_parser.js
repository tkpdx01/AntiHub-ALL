/**
 * Gemini SSE 解析（行缓冲 + JSON 拆包不丢事件）。
 *
 * 说明：
 * - 输入是“已经 decode 成字符串”的 chunk（负责跨 chunk 拼接）
 * - 仅解析 `data: <json>` 行；其它 SSE 字段忽略
 * - 解析失败只计数，不抛异常（避免单条坏包打断整条流）
 */

export function createGeminiSseParser(callback, options = {}) {
  const maxBufferSize =
    typeof options.maxBufferSize === 'number' && options.maxBufferSize > 0
      ? options.maxBufferSize
      : 1024 * 1024;

  let sseBuffer = '';
  let reasoningContent = ''; // 累积 reasoning_content
  let toolCalls = [];
  let parseErrorCount = 0;

  const processSseLine = (line) => {
    const trimmedLine = typeof line === 'string' ? line.trim() : '';
    if (!trimmedLine.startsWith('data:')) return;

    const jsonStr = trimmedLine.slice('data:'.length).trim();
    if (!jsonStr || jsonStr === '[DONE]') return;

    try {
      const data = JSON.parse(jsonStr);

      const parts = data.response?.candidates?.[0]?.content?.parts;
      if (parts) {
        for (const part of parts) {
          if (part.thought === true) {
            // Gemini 的思考内容转换为 OpenAI 兼容的 reasoning_content 格式
            reasoningContent += part.text || '';
            callback({ type: 'reasoning', content: part.text || '' });
          } else if (part.text !== undefined) {
            // 过滤掉空的非thought文本
            if (part.text.trim() === '') {
              continue;
            }
            callback({ type: 'text', content: part.text });
          } else if (part.functionCall) {
            toolCalls.push({
              id: part.functionCall.id,
              type: 'function',
              function: {
                name: part.functionCall.name,
                arguments: JSON.stringify(part.functionCall.args)
              }
            });
          }
        }
      }

      // 当遇到 finishReason 时，发送所有收集的工具调用
      if (data.response?.candidates?.[0]?.finishReason && toolCalls.length > 0) {
        callback({ type: 'tool_calls', tool_calls: toolCalls });
        toolCalls = [];
      }
    } catch {
      // 理论上这里不应该频繁发生（我们已经做了跨 chunk 的按行缓冲）。
      parseErrorCount++;
    }
  };

  const drainLines = () => {
    let newlineIndex;
    while ((newlineIndex = sseBuffer.indexOf('\n')) !== -1) {
      const line = sseBuffer.slice(0, newlineIndex);
      sseBuffer = sseBuffer.slice(newlineIndex + 1);
      processSseLine(line);
    }
  };

  return {
    feed(chunkText) {
      sseBuffer += String(chunkText ?? '');

      if (sseBuffer.length > maxBufferSize) {
        sseBuffer = sseBuffer.slice(-maxBufferSize);
      }

      drainLines();
    },

    flush() {
      drainLines();
      if (sseBuffer.trim()) {
        processSseLine(sseBuffer);
      }
      sseBuffer = '';

      return {
        parseErrorCount,
        reasoningContent,
      };
    }
  };
}

