import type { ReactNode } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { Result, Spin } from 'antd'
import { useAuth } from '../contexts/AuthContext'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

export function PermissionGate({ code, children }: { code: string; children: ReactNode }) {
  const { can } = useAuth()
  if (!can(code)) {
    return <Result status="403" title="403" subTitle="您没有权限访问该功能。" />
  }
  return <>{children}</>
}
