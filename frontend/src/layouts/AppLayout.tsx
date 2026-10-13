import { useMemo, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Avatar, Dropdown, Layout, Menu, Tag } from 'antd'
import type { MenuProps } from 'antd'
import {
  AppstoreOutlined,
  AuditOutlined,
  DashboardOutlined,
  KeyOutlined,
  LinkOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useAuth } from '../contexts/AuthContext'

const { Header, Sider, Content } = Layout

interface MenuEntry {
  key: string
  label: string
  icon: React.ReactNode
  permission: string
}

const MENU: MenuEntry[] = [
  { key: '/dashboard', label: '仪表盘', icon: <DashboardOutlined />, permission: 'dashboard:read' },
  { key: '/accounts/users', label: '用户管理', icon: <UserOutlined />, permission: 'user:read' },
  { key: '/accounts/groups', label: '用户组', icon: <TeamOutlined />, permission: 'group:read' },
  { key: '/accounts/orgs', label: '组织架构', icon: <AppstoreOutlined />, permission: 'org:read' },
  { key: '/authz/apps', label: '设备管理', icon: <AppstoreOutlined />, permission: 'application:read' },
  { key: '/authz/tools', label: '连接工具', icon: <LinkOutlined />, permission: 'application:read' },
  { key: '/authz/roles', label: '角色权限', icon: <SafetyCertificateOutlined />, permission: 'role:read' },
  { key: '/authz/policies', label: '访问策略', icon: <SafetyCertificateOutlined />, permission: 'policy:read' },
  { key: '/audit', label: '审计日志', icon: <AuditOutlined />, permission: 'audit:read' },
  { key: '/vault/secrets', label: '密码托管', icon: <KeyOutlined />, permission: 'secret:read' },
  { key: '/vault/rotations', label: '自动轮换', icon: <KeyOutlined />, permission: 'secret:read' },
]

export default function AppLayout() {
  const { user, can, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const items = useMemo(
    () =>
      MENU.filter((m) => can(m.permission)).map((m) => ({
        key: m.key,
        icon: m.icon,
        label: <Link to={m.key}>{m.label}</Link>,
      })),
    [can],
  )

  const selectedKey = useMemo(() => {
    const matched = MENU.filter((m) => location.pathname.startsWith(m.key))
    return matched.length ? matched[matched.length - 1].key : '/dashboard'
  }, [location.pathname])

  const userMenu: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: '个人中心' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ]

  const onUserMenuClick: MenuProps['onClick'] = async ({ key }) => {
    if (key === 'profile') {
      navigate('/profile')
    } else if (key === 'logout') {
      await logout()
      navigate('/login')
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="dark">
        <div style={{ height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span className="brand-logo">{collapsed ? '4A' : 'lycloud4A'}</span>
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={items} />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 600 }}>lycloud4A 统一身份认证与访问管理</span>
          <Dropdown menu={{ items: userMenu, onClick: onUserMenuClick }} placement="bottomRight">
            <span style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Avatar size="small" icon={<UserOutlined />} />
              <span>{user?.display_name || user?.username}</span>
              {user?.is_superuser && <Tag color="gold">超管</Tag>}
              {user?.mfa_enabled && <Tag color="green">MFA</Tag>}
            </span>
          </Dropdown>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
