export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Message {
  message: string
}

export interface UserOut {
  id: number
  username: string
  display_name: string | null
  email: string | null
  phone: string | null
  status: string
  is_superuser: boolean
  mfa_enabled: boolean
  org_id: number | null
  last_login_at: string | null
  created_at: string
}

export interface MeOut {
  id: number
  username: string
  display_name: string | null
  email: string | null
  status: string
  is_superuser: boolean
  mfa_enabled: boolean
  org_id: number | null
  roles: RoleBrief[]
  permissions: string[]
}

export interface RoleBrief {
  id: number
  code: string
  name: string
}

export interface OrgOut {
  id: number
  name: string
  code: string
  parent_id: number | null
  description: string | null
  sort_order: number
}

export interface OrgTreeNode extends OrgOut {
  children?: OrgTreeNode[]
}

export interface GroupOut {
  id: number
  name: string
  code: string
  description: string | null
  member_count: number
}

export interface PermissionOut {
  id: number
  code: string
  name: string
  resource: string
  action: string
  description: string | null
}

export interface RoleOut {
  id: number
  code: string
  name: string
  description: string | null
  is_builtin: boolean
  application_id: number | null
}

export interface RoleDetailOut extends RoleOut {
  permissions: PermissionOut[]
}

export interface ApplicationOut {
  id: number
  code: string
  name: string
  description: string | null
  app_type: string
  protocol: string
  url: string | null
  login_username: string | null
  credential_type: string | null
  has_credential: boolean
  conn_status: string
  last_checked_at: string | null
  last_check_error: string | null
  owner: string | null
  status: boolean
  icon: string | null
}

export interface AppCheckResult {
  app_id: number
  conn_status: string
  last_checked_at: string
  error: string | null
}

export interface LaunchToolOut {
  id: number
  kind: string
  name: string
  exe_path: string
  protocols: string | null
  description: string | null
  status: boolean
}

export interface AppConnectOut {
  ticket: string
  agent_url: string
  device_id: number
  device_name: string
  tool_kind: string
}

export interface PolicyOut {
  id: number
  name: string
  description: string | null
  effect: string
  priority: number
  subject_type: string
  subject_id: number | null
  resource_type: string
  resource_id: number | null
  actions: string[]
  conditions: Record<string, unknown>
  enabled: boolean
}

export interface AuditOut {
  id: number
  timestamp: string
  category: string
  action: string
  result: string
  actor_id: number | null
  actor_username: string | null
  target_type: string | null
  target_id: number | null
  target_name: string | null
  device_type?: string | null
  connect_tool?: string | null
  log_file_path?: string | null
  has_log_content?: boolean
  actor_ip: string | null
  user_agent: string | null
  message: string | null
  detail: Record<string, unknown> | null
  request_id: string | null
}

export interface AuditStats {
  total: number
  success: number
  failure: number
  by_category: Record<string, number>
  by_day: { date: string; count: number }[]
}

export interface SecretOut {
  id: number
  name: string
  category: string
  description: string | null
  owner: string | null
  tags: Record<string, string>
  path: string
  current_version: number
  rotation_enabled: boolean
  rotation_type: string
  rotation_interval_days: number | null
  next_rotation_at: string | null
  last_rotated_at: string | null
  last_rotation_status: string | null
  last_rotation_error: string | null
  rotate_target: string | null
  rotate_username: string | null
  status: boolean
}

export interface SecretVersionOut {
  id: number
  version: number
  created_at: string
  created_by: string | null
  comment: string | null
}

export interface SecretValueOut {
  path: string
  version: number
  data: Record<string, string>
  masked: Record<string, string>
}

export interface RotateResult {
  path: string
  success: boolean
  new_version: number | null
  message: string
}

export interface RotationItemResult {
  path: string
  success: boolean
  new_version: number | null
  message: string
}

export interface RotationRunResult {
  processed: number
  succeeded: number
  failed: number
  results: RotationItemResult[]
}

export interface DashboardStats {
  user_total: number
  user_active: number
  user_disabled: number
  app_total: number
  role_total: number
  policy_total: number
  secret_total: number
  secret_rotation_due: number
  login_today: number
  login_failed_today: number
  audit_total: number
  login_trend: { date: string; count: number }[]
  category_distribution: { category: string; count: number }[]
  recent_audits: {
    id: number
    timestamp: string | null
    category: string
    action: string
    result: string
    actor_username: string | null
    target_name: string | null
    message: string | null
  }[]
  mfa_enabled_rate: number
}

export interface LoginResult {
  mfa_required: boolean
  mfa_token?: string
  access_token?: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
}
