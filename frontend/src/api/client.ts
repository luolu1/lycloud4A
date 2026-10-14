import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const ACCESS_KEY = '4a_access_token'
const REFRESH_KEY = '4a_refresh_token'

export const tokenStore = {
  getAccess(): string | null {
    return localStorage.getItem(ACCESS_KEY)
  },
  getRefresh(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },
  set(access: string, refresh: string): void {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear(): void {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 这些接口本身不依赖访问令牌，401 时不应触发刷新逻辑
const NO_REFRESH_PATHS = ['/auth/login', '/auth/refresh', '/auth/mfa/verify', '/auth/logout']

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
  _netRetry?: number
}

// 只对幂等请求做瞬时故障重试，避免重复提交业务操作
const IDEMPOTENT_METHODS = new Set(['get', 'head', 'options'])
// 网关/限流类状态码，通常属于瞬时故障，可安全重试
const RETRYABLE_STATUS = new Set([429, 502, 503, 504])
// 每次重试前的等待时间（毫秒），长度即最大重试次数
const NETWORK_RETRY_DELAYS = [400, 1200]

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** 是否为可重试的瞬时故障：无响应（断网、代理重置）或网关类错误码 */
function isRetryableError(error: AxiosError): boolean {
  if (error.code === 'ERR_CANCELED') return false
  if (error.response) return RETRYABLE_STATUS.has(error.response.status)
  return true
}

/** 是否为认证类错误（令牌失效/无权限） */
export function isAuthError(err: unknown): boolean {
  const status = (err as AxiosError | undefined)?.response?.status
  return status === 401 || status === 403
}

let refreshInFlight: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  const refreshToken = tokenStore.getRefresh()
  if (!refreshToken) return null
  try {
    const resp = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
    const data = resp.data as { access_token: string; refresh_token: string }
    tokenStore.set(data.access_token, data.refresh_token)
    return data.access_token
  } catch {
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined
    const status = error.response?.status
    const url = original?.url ?? ''

    // 1) 访问令牌过期：静默刷新后重放原请求（包括 /auth/me，避免过期即被登出）
    if (
      status === 401 &&
      original &&
      !original._retry &&
      !NO_REFRESH_PATHS.some((p) => url.includes(p))
    ) {
      original._retry = true
      if (!refreshInFlight) {
        refreshInFlight = doRefresh().finally(() => {
          refreshInFlight = null
        })
      }
      const newToken = await refreshInFlight
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
      tokenStore.clear()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    // 2) 幂等请求遇到瞬时故障：自动重试，避免偶发 “Network Error” 打断用户
    if (
      original &&
      isRetryableError(error) &&
      IDEMPOTENT_METHODS.has((original.method ?? 'get').toLowerCase())
    ) {
      const attempt = original._netRetry ?? 0
      if (attempt < NETWORK_RETRY_DELAYS.length) {
        original._netRetry = attempt + 1
        await sleep(NETWORK_RETRY_DELAYS[attempt])
        return api(original)
      }
    }

    return Promise.reject(error)
  },
)

export function extractError(err: unknown, fallback = '请求失败'): string {
  const axiosErr = err as AxiosError<{ detail?: string | { msg?: string }[] }>
  const detail = axiosErr.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) return detail[0].msg
  if (axiosErr.code === 'ERR_CANCELED') return '请求已取消'
  if (!axiosErr.response) {
    if (axiosErr.code === 'ECONNABORTED' || axiosErr.code === 'ETIMEDOUT') {
      return '请求超时，请检查网络后重试'
    }
    return '网络连接不稳定，请稍后重试'
  }
  const status = axiosErr.response.status
  if (status >= 500) return '服务暂时不可用，请稍后重试'
  if (status === 429) return '操作过于频繁，请稍后重试'
  return axiosErr.message || fallback
}

export async function callConnectAgent(
  agentUrl: string,
  ticket: string,
): Promise<{ device?: string; tool?: string }> {
  const resp = await fetch(`${agentUrl.replace(/\/$/, '')}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket, platform: window.location.origin }),
  })
  if (!resp.ok) {
    const data = (await resp.json().catch(() => ({}))) as { error?: string }
    throw new Error(data.error || `连接助手返回 ${resp.status}`)
  }
  return resp.json() as Promise<{ device?: string; tool?: string }>
}

export async function detectAgentTool(
  agentUrl: string,
  exePath: string,
): Promise<{ installed: boolean; exe_path: string }> {
  const resp = await fetch(`${agentUrl.replace(/\/$/, '')}/detect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exe_path: exePath }),
  })
  if (!resp.ok) throw new Error(`连接助手返回 ${resp.status}`)
  return resp.json() as Promise<{ installed: boolean; exe_path: string }>
}

export async function fetchAgentHealth(
  agentUrl: string,
): Promise<{ status: string; agent: string; version: string }> {
  const resp = await fetch(`${agentUrl.replace(/\/$/, '')}/health`)
  if (!resp.ok) throw new Error(`连接助手返回 ${resp.status}`)
  return resp.json() as Promise<{ status: string; agent: string; version: string }>
}

export default api
