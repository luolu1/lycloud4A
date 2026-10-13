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
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    const status = error.response?.status
    const url = original?.url ?? ''
    if (status === 401 && original && !original._retry && !url.includes('/auth/')) {
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
    }
    return Promise.reject(error)
  },
)

export function extractError(err: unknown, fallback = '请求失败'): string {
  const axiosErr = err as AxiosError<{ detail?: string | { msg?: string }[] }>
  const detail = axiosErr.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) return detail[0].msg
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

export default api
