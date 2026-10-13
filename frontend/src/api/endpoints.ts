import api from './client'
import type {
  AppCheckResult,
  AppConnectOut,
  ApplicationOut,
  AuditOut,
  AuditStats,
  DashboardStats,
  GroupOut,
  LaunchToolOut,
  LoginResult,
  MeOut,
  Message,
  OrgOut,
  OrgTreeNode,
  Page,
  PermissionOut,
  PolicyOut,
  RoleDetailOut,
  RoleOut,
  RotateResult,
  RotationRunResult,
  SecretOut,
  SecretValueOut,
  SecretVersionOut,
  UserOut,
} from '../types'

export const authApi = {
  login: (body: { username: string; password: string }) =>
    api.post<LoginResult>('/auth/login', body).then((r) => r.data),
  verifyMfa: (body: { mfa_token: string; code: string }) =>
    api.post<LoginResult>('/auth/mfa/verify', body).then((r) => r.data),
  me: () => api.get<MeOut>('/auth/me').then((r) => r.data),
  logout: (body: { refresh_token?: string }) =>
    api.post<Message>('/auth/logout', body).then((r) => r.data),
  changePassword: (body: { old_password: string; new_password: string }) =>
    api.post<Message>('/auth/change-password', body).then((r) => r.data),
  mfaSetup: () =>
    api.post<{ secret: string; otpauth_url: string }>('/auth/mfa/setup').then((r) => r.data),
  mfaEnable: (body: { code: string }) =>
    api.post<Message>('/auth/mfa/enable', body).then((r) => r.data),
  mfaDisable: (body: { code: string }) =>
    api.post<Message>('/auth/mfa/disable', body).then((r) => r.data),
}

export const userApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<Page<UserOut>>('/users', { params }).then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<UserOut>('/users', body).then((r) => r.data),
  get: (id: number) => api.get<UserOut>(`/users/${id}`).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<UserOut>(`/users/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/users/${id}`).then((r) => r.data),
  resetPassword: (id: number, body: { new_password: string }) =>
    api.post<Message>(`/users/${id}/reset-password`, body).then((r) => r.data),
  setRoles: (id: number, role_ids: number[]) =>
    api.post<Message>(`/users/${id}/roles`, { role_ids }).then((r) => r.data),
}

export const groupApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<Page<GroupOut>>('/groups', { params }).then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<GroupOut>('/groups', body).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<GroupOut>(`/groups/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/groups/${id}`).then((r) => r.data),
}

export const orgApi = {
  list: () => api.get<OrgOut[]>('/orgs').then((r) => r.data),
  tree: () => api.get<OrgTreeNode[]>('/orgs/tree').then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<OrgOut>('/orgs', body).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<OrgOut>(`/orgs/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/orgs/${id}`).then((r) => r.data),
}

export const appApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<Page<ApplicationOut>>('/apps', { params }).then((r) => r.data),
  launchable: () => api.get<ApplicationOut[]>('/apps/launchable').then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<ApplicationOut>('/apps', body).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<ApplicationOut>(`/apps/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/apps/${id}`).then((r) => r.data),
  launch: (id: number) =>
    api.post<{ url: string; sso_ticket?: string | null }>(`/apps/${id}/launch`).then((r) => r.data),
  check: (id: number) => api.post<AppCheckResult>(`/apps/${id}/check`).then((r) => r.data),
  connect: (id: number, tool_id: number, agent_url?: string, client_ip?: string) =>
    api.post<AppConnectOut>(`/apps/${id}/connect`, { tool_id, agent_url, client_ip }).then((r) => r.data),
}

export const toolApi = {
  list: () => api.get<LaunchToolOut[]>('/tools').then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<LaunchToolOut>('/tools', body).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<LaunchToolOut>(`/tools/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/tools/${id}`).then((r) => r.data),
}

export const roleApi = {
  list: () => api.get<RoleOut[]>('/roles').then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<RoleDetailOut>('/roles', body).then((r) => r.data),
  get: (id: number) => api.get<RoleDetailOut>(`/roles/${id}`).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<RoleDetailOut>(`/roles/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/roles/${id}`).then((r) => r.data),
  setPermissions: (id: number, permission_ids: number[]) =>
    api.post<Message>(`/roles/${id}/permissions`, { permission_ids }).then((r) => r.data),
  permissions: () => api.get<PermissionOut[]>('/permissions').then((r) => r.data),
}

export const policyApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<Page<PolicyOut>>('/policies', { params }).then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<PolicyOut>('/policies', body).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<PolicyOut>(`/policies/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/policies/${id}`).then((r) => r.data),
  evaluate: (body: Record<string, unknown>) =>
    api
      .post<{ allowed: boolean; matched_policy: string | null; reason: string }>(
        '/policies/evaluate',
        body,
      )
      .then((r) => r.data),
}

export const auditApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<Page<AuditOut>>('/audits', { params }).then((r) => r.data),
  stats: (params?: Record<string, unknown>) =>
    api.get<AuditStats>('/audits/stats', { params }).then((r) => r.data),
  logContent: (auditId: number) =>
    api.get<{ content: string | null; path: string | null; error: string | null }>(`/audits/${auditId}/log-content`).then((r) => r.data),
}

export const secretApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<Page<SecretOut>>('/secrets', { params }).then((r) => r.data),
  create: (body: Record<string, unknown>) =>
    api.post<SecretOut>('/secrets', body).then((r) => r.data),
  get: (id: number) => api.get<SecretOut>(`/secrets/${id}`).then((r) => r.data),
  update: (id: number, body: Record<string, unknown>) =>
    api.put<SecretOut>(`/secrets/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete<Message>(`/secrets/${id}`).then((r) => r.data),
  value: (id: number, params?: { version?: number; reveal?: boolean }) =>
    api.get<SecretValueOut>(`/secrets/${id}/value`, { params }).then((r) => r.data),
  setValue: (id: number, body: { data: Record<string, string>; comment?: string }) =>
    api.post<SecretOut>(`/secrets/${id}/value`, body).then((r) => r.data),
  versions: (id: number) =>
    api.get<SecretVersionOut[]>(`/secrets/${id}/versions`).then((r) => r.data),
  rotate: (id: number) => api.post<RotateResult>(`/secrets/${id}/rotate`).then((r) => r.data),
}

export const rotationApi = {
  due: () => api.get<SecretOut[]>('/rotations/due').then((r) => r.data),
  run: () => api.post<RotationRunResult>('/rotations/run').then((r) => r.data),
}

export const dashboardApi = {
  stats: () => api.get<DashboardStats>('/dashboard/stats').then((r) => r.data),
}
