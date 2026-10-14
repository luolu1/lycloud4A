import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { roleApi, userApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { RoleOut, UserOut } from '../../types'
import { formatDateTime } from '../../utils/format'

const { Title } = Typography

const statusColor: Record<string, string> = { active: 'green', disabled: 'red', locked: 'orange' }

export default function UsersPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<UserOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [roles, setRoles] = useState<RoleOut[]>([])

  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<UserOut | null>(null)
  const [form] = Form.useForm()

  const [pwdUser, setPwdUser] = useState<UserOut | null>(null)
  const [pwdForm] = Form.useForm()

  const [rolesUser, setRolesUser] = useState<UserOut | null>(null)
  const [roleIds, setRoleIds] = useState<number[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await userApi.list({ page, page_size: pageSize, q: q || undefined })
      setData(resp.items)
      setTotal(resp.total)
    } catch (err) {
      message.error(extractError(err, '加载用户失败'))
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, q, message])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void (async () => {
      try {
        setRoles(await roleApi.list())
      } catch {
        /* roles optional for display */
      }
    })()
  }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ status: 'active' })
    setEditOpen(true)
  }

  const openEdit = (record: UserOut) => {
    setEditing(record)
    form.setFieldsValue({
      username: record.username,
      display_name: record.display_name,
      email: record.email,
      phone: record.phone,
      status: record.status,
      password: undefined,
    })
    setEditOpen(true)
  }

  const submitEdit = async () => {
    const values = await form.validateFields()
    const payload: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(values)) {
      if (typeof v === 'string') {
        const trimmed = v.trim()
        if (trimmed) payload[k] = trimmed
      } else if (v !== undefined && v !== null) {
        payload[k] = v
      }
    }
    try {
      if (editing) {
        const { password, username, ...rest } = payload
        void password
        void username
        await userApi.update(editing.id, rest)
        message.success('用户已更新')
      } else {
        await userApi.create(payload)
        message.success('用户已创建')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const submitPassword = async () => {
    if (!pwdUser) return
    const values = await pwdForm.validateFields()
    try {
      await userApi.resetPassword(pwdUser.id, { new_password: values.new_password })
      message.success('密码已重置')
      setPwdUser(null)
      pwdForm.resetFields()
    } catch (err) {
      message.error(extractError(err, '重置失败'))
    }
  }

  const submitRoles = async () => {
    if (!rolesUser) return
    try {
      await userApi.setRoles(rolesUser.id, roleIds)
      message.success('角色已更新')
      setRolesUser(null)
    } catch (err) {
      message.error(extractError(err, '更新角色失败'))
    }
  }

  const toggleStatus = async (record: UserOut) => {
    const next = record.status === 'active' ? 'disabled' : 'active'
    try {
      await userApi.update(record.id, { status: next })
      message.success('状态已更新')
      await load()
    } catch (err) {
      message.error(extractError(err, '更新状态失败'))
    }
  }

  const remove = async (record: UserOut) => {
    try {
      await userApi.remove(record.id)
      message.success('用户已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const columns: ColumnsType<UserOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '用户名', dataIndex: 'username' },
    { title: '显示名', dataIndex: 'display_name', render: (v) => v || '-' },
    { title: '邮箱', dataIndex: 'email', render: (v) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => <Tag color={statusColor[v] || 'default'}>{v}</Tag>,
    },
    {
      title: 'MFA',
      dataIndex: 'mfa_enabled',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">开</Tag> : <Tag>关</Tag>),
    },
    {
      title: '超管',
      dataIndex: 'is_superuser',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="gold">是</Tag> : '-'),
    },
    { title: '最近登录', dataIndex: 'last_login_at', render: (v) => formatDateTime(v) },
    {
      title: '操作',
      width: 300,
      fixed: 'right',
      render: (_v, record) => (
        <Space size="small" wrap>
          {can('user:write') && <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>}
          {can('user:write') && (
            <Button type="link" size="small" onClick={() => { setRolesUser(record); setRoleIds([]) }}>
              分配角色
            </Button>
          )}
          {can('user:write') && (
            <Button type="link" size="small" onClick={() => void toggleStatus(record)}>
              {record.status === 'active' ? '停用' : '启用'}
            </Button>
          )}
          {can('user:reset_password') && (
            <Button type="link" size="small" onClick={() => { setPwdUser(record); pwdForm.resetFields() }}>
              重置密码
            </Button>
          )}
          {can('user:delete') && (
            <Popconfirm title="确认删除该用户？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} className="page-title">用户管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索用户名/邮箱"
          style={{ width: 260 }}
          onSearch={(value) => { setPage(1); setQ(value) }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('user:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建用户</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        scroll={{ x: 1200 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps) },
        }}
      />

      <Modal
        title={editing ? '编辑用户' : '新建用户'}
        open={editOpen}
        onOk={submitEdit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input disabled={!!editing} placeholder="3-64位字母、数字或符号" />
          </Form.Item>
          {!editing && (
            <Form.Item
              name="password"
              label="初始密码"
              rules={[{ required: true, min: 12, message: '至少 12 位（须包含大小写字母、数字和特殊符号）' }]}
            >
              <Input.Password placeholder="至少 12 位（含大小写字母、数字和符号）" />
            </Form.Item>
          )}
          <Form.Item name="display_name" label="显示名">
            <Input placeholder="选填，如不填写则默认同用户名" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="选填，如 user@example.com" />
          </Form.Item>
          <Form.Item name="phone" label="手机号"><Input placeholder="选填" /></Form.Item>
          <Form.Item name="status" label="状态" initialValue="active">
            <Select
              options={[
                { value: 'active', label: '启用' },
                { value: 'disabled', label: '停用' },
                { value: 'locked', label: '锁定' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重置密码 - ${pwdUser?.username ?? ''}`}
        open={!!pwdUser}
        onOk={submitPassword}
        onCancel={() => setPwdUser(null)}
        destroyOnClose
      >
        <Form form={pwdForm} layout="vertical">
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[{ required: true, min: 12, message: '至少 12 位（须包含大小写字母、数字和特殊符号）' }]}
          >
            <Input.Password placeholder="至少 12 位（含大小写字母、数字和符号）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`分配角色 - ${rolesUser?.username ?? ''}`}
        open={!!rolesUser}
        onOk={submitRoles}
        onCancel={() => setRolesUser(null)}
        destroyOnClose
      >
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="选择角色"
          value={roleIds}
          onChange={setRoleIds}
          options={roles.map((r) => ({ value: r.id, label: `${r.name} (${r.code})` }))}
        />
      </Modal>
    </div>
  )
}
