import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { authApi } from '../api/endpoints'
import { isAuthError, tokenStore } from '../api/client'
import type { LoginResult, MeOut } from '../types'

interface AuthContextValue {
  user: MeOut | null
  loading: boolean
  login: (username: string, password: string) => Promise<LoginResult>
  verifyMfa: (mfaToken: string, code: string) => Promise<void>
  logout: () => Promise<void>
  reload: () => Promise<void>
  can: (code: string) => boolean
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeOut | null>(null)
  const [loading, setLoading] = useState(true)

  const loadMe = useCallback(async () => {
    if (!tokenStore.getAccess()) {
      setUser(null)
      return
    }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch (err) {
      // 仅在认证确实失效时登出；瞬时网络错误保留当前登录态，避免误登出
      if (isAuthError(err)) {
        tokenStore.clear()
        setUser(null)
      }
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadMe()
      setLoading(false)
    })()
  }, [loadMe])

  const login = useCallback(async (username: string, password: string) => {
    const result = await authApi.login({ username, password })
    if (!result.mfa_required && result.access_token && result.refresh_token) {
      tokenStore.set(result.access_token, result.refresh_token)
      await loadMe()
    }
    return result
  }, [loadMe])

  const verifyMfa = useCallback(
    async (mfaToken: string, code: string) => {
      const result = await authApi.verifyMfa({ mfa_token: mfaToken, code })
      if (result.access_token && result.refresh_token) {
        tokenStore.set(result.access_token, result.refresh_token)
        await loadMe()
      }
    },
    [loadMe],
  )

  const logout = useCallback(async () => {
    const refresh = tokenStore.getRefresh()
    try {
      if (refresh) await authApi.logout({ refresh_token: refresh })
    } catch {
      /* ignore network errors on logout */
    }
    tokenStore.clear()
    setUser(null)
  }, [])

  const can = useCallback(
    (code: string) => {
      if (!user) return false
      return user.is_superuser || user.permissions.includes('*') || user.permissions.includes(code)
    },
    [user],
  )

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, verifyMfa, logout, reload: loadMe, can }),
    [user, loading, login, verifyMfa, logout, loadMe, can],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}
