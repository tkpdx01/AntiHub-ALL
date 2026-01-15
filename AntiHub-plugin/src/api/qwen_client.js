import logger from '../utils/logger.js';
import qwenAccountService from '../services/qwen_account.service.js';
import qwenService from '../services/qwen.service.js';

const QWEN_DEFAULT_BASE_URL = 'https://portal.qwen.ai/v1';
const QWEN_USER_AGENT = 'google-api-nodejs-client/9.15.1';
const QWEN_X_GOOG_API_CLIENT = 'gl-node/22.17.0';
const QWEN_CLIENT_METADATA = 'ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI';

class QwenClient {
  getAvailableModels() {
    const created = Math.floor(Date.now() / 1000);
    return {
      object: 'list',
      data: [
        { id: 'qwen3-coder-plus', object: 'model', created, owned_by: 'qwen' },
        { id: 'qwen3-coder-flash', object: 'model', created, owned_by: 'qwen' },
        { id: 'vision-model', object: 'model', created, owned_by: 'qwen' },
      ],
    };
  }

  resolveBaseURL(account) {
    const resource = qwenService.normalizeResourceURL(account?.resource_url);
    if (!resource) return QWEN_DEFAULT_BASE_URL;
    return `https://${resource}/v1`;
  }

  buildHeaders(accessToken, stream) {
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      'User-Agent': QWEN_USER_AGENT,
      'X-Goog-Api-Client': QWEN_X_GOOG_API_CLIENT,
      'Client-Metadata': QWEN_CLIENT_METADATA,
      Accept: stream ? 'text/event-stream' : 'application/json',
    };
  }

  /**
   * 获取一个可用账号（不做配额检查，只有状态/need_refresh/token有效性）
   * @param {string} user_id
   * @param {Object} user
   * @param {Array<string>} excludeAccountIds
   * @returns {Promise<Object>}
   */
  async getAvailableAccount(user_id, user, excludeAccountIds = []) {
    const preferShared = user?.prefer_shared ?? 0;
    let accounts = [];

    if (preferShared === 1) {
      const shared = await qwenAccountService.getAvailableAccounts(null, 1);
      const dedicated = await qwenAccountService.getAvailableAccounts(user_id, 0);
      accounts = shared.concat(dedicated);
    } else {
      const dedicated = await qwenAccountService.getAvailableAccounts(user_id, 0);
      const shared = await qwenAccountService.getAvailableAccounts(null, 1);
      accounts = dedicated.concat(shared);
    }

    if (excludeAccountIds.length > 0) {
      accounts = accounts.filter(acc => !excludeAccountIds.includes(acc.account_id));
    }

    if (accounts.length === 0) {
      throw new Error('没有可用的Qwen账号，请先导入账号');
    }

    // 随机选一个，避免热点
    const account = accounts[Math.floor(Math.random() * accounts.length)];

    // 过期则尝试 refresh
    if (qwenAccountService.isTokenExpired(account)) {
      const rt = typeof account.refresh_token === 'string' ? account.refresh_token.trim() : '';
      if (!rt) {
        await qwenAccountService.markAccountNeedRefresh(account.account_id);
        const nextExclude = [...excludeAccountIds, account.account_id];
        return this.getAvailableAccount(user_id, user, nextExclude);
      }

      try {
        const tokenData = await qwenService.refreshAccessToken(rt);
        const expiresAt =
          typeof tokenData.expires_in === 'number'
            ? Date.now() + tokenData.expires_in * 1000
            : null;
        const updated = await qwenAccountService.updateAccountToken(account.account_id, {
          access_token: tokenData.access_token,
          refresh_token: tokenData.refresh_token,
          expires_at: expiresAt,
          last_refresh: new Date().toISOString(),
          resource_url: tokenData.resource_url,
        });
        return updated;
      } catch (error) {
        // refresh 失败：invalid_grant 直接标记需要重新授权；否则也降级
        if (error?.isInvalidGrant) {
          await qwenAccountService.markAccountNeedRefresh(account.account_id);
        } else {
          await qwenAccountService.markAccountNeedRefresh(account.account_id);
        }
        const nextExclude = [...excludeAccountIds, account.account_id];
        return this.getAvailableAccount(user_id, user, nextExclude);
      }
    }

    return account;
  }

  /**
   * 发起上游请求（返回 fetch Response）
   * 内部会做：挑账号、必要时刷新token、401/403/429 简单换号重试
   * @param {Object} params
   * @param {string} params.user_id
   * @param {Object} params.user
   * @param {Object} params.body - OpenAI chat/completions 请求体
   * @param {AbortSignal} params.signal
   * @param {Array<string>} params.excludeAccountIds
   */
  async requestChatCompletions({ user_id, user, body, signal, excludeAccountIds = [] }) {
    const stream = !!body?.stream;
    const account = await this.getAvailableAccount(user_id, user, excludeAccountIds);
    const baseURL = this.resolveBaseURL(account);
    const url = `${baseURL.replace(/\/$/, '')}/chat/completions`;

    const resp = await fetch(url, {
      method: 'POST',
      headers: this.buildHeaders(account.access_token, stream),
      body: JSON.stringify(body),
      signal,
    });

    if (resp.status === 401 || resp.status === 403) {
      // 账号不可用：直接禁用并换号
      try {
        await qwenAccountService.updateAccountStatus(account.account_id, 0);
      } catch {}
      const nextExclude = [...excludeAccountIds, account.account_id];
      if (nextExclude.length >= 3) {
        return resp;
      }
      return this.requestChatCompletions({ user_id, user, body, signal, excludeAccountIds: nextExclude });
    }

    if (resp.status === 429) {
      // 429 先不禁用，直接换号尝试（避免某个账号瞬时被打爆）
      const nextExclude = [...excludeAccountIds, account.account_id];
      if (nextExclude.length >= 3) {
        return resp;
      }
      return this.requestChatCompletions({ user_id, user, body, signal, excludeAccountIds: nextExclude });
    }

    return resp;
  }
}

const qwenClient = new QwenClient();
export default qwenClient;
