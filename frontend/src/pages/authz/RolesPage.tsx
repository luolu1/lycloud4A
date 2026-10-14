import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
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
  Tree,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { roleApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { PermissionOut, RoleDetailOut, RoleOut } from '../../types'

const { Title } = Typography

interface PermissionTreeNode {
  key: string
  title: string
  children?: PermissionTreeNode[]
}

function buildPermissionTree(perms: PermissionOut[]): PermissionTreeNode[] {
  const groups = new Map<string, PermissionTreeNode>()
  for (const p of perms) {
    let node = groups.get(p.resource)
    if (!node) {
      node = { key: `res:${p.resource}`, title: p.resource, children: [] }
      groups.set(p.resource, node)
    }
    node.children!.push({ key: String(p.id), title: p.description ? `${p.name} - ${p.description}` : p.name })
  }
  return Array.from(groups.values())
}

export default function RolesPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<RoleOut[]>([])
  const [loading, setLoading] = useState(false)
  const [permissions, setPermissions] = useState<PermissionOut[]>([])

  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<RoleOut | null>(null)
  const [form] = Form.useForm()

  const [permRole, setPermRole] = useState<RoleDetailOut | null>(null)
  const [checkedKeys, setCheckedKeys] = useState<string[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await roleApi.list())
    } catch (err) {
      message.error(extractError(err, '加载角色失败'))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void (async () => {
      try {
        setPermissions(await roleApi.permissions())
      } catch {
        /* permission list optional */
      }
    })()
  }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setEditOpen(true)
  }

  const openEdit = (record: RoleOut) => {
    setEditing(record)
    form.setFieldsValue(record)
    setEditOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await roleApi.update(editing.id, values)
        message.success('角色已更新')
      } else {
        await roleApi.create(values)
        message.success('角色已创建')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: RoleOut) => {
    try {
      await roleApi.remove(record.id)
      message.success('角色已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const openPermissions = async (record: RoleOut) => {
    try {
      const detail = await roleApi.get(record.id)
      setPermRole(detail)
      setCheckedKeys(detail.permissions.map((p) => String(p.id)))
    } catch (err) {
      message.error(extractError(err, '加载角色详情失败'))
    }
  }

  const submitPermissions = async () => {
    if (!permRole) return
    try {
      const numericKeys = checkedKeys
        .filter((k) => !String(k).startsWith('res:'))
        .map((k) => Number(k))
        .filter((n) => !Number.isNaN(n))
      await roleApi.setPermissions(permRole.id, numericKeys)
      message.success('角色权限已更新')
      setPermRole(null)
    } catch (err) {
      message.error(extractError(err, '更新权限失败'))
    }
  }

  const columns: ColumnsType<RoleOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    { title: '编码', dataIndex: 'code' },
    { title: '描述', dataIndex: 'description', render: (v) => v || '-' },
    {
      title: '内置',
      dataIndex: 'is_builtin',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="blue">内置</Tag> : '-'),
    },
    {
      title: '操作',
      width: 220,
      render: (_v, record) => (
        <Space size="small" wrap>
          {can('role:read') && (
            <Button type="link" size="small" onClick={() => void openPermissions(record)}>配置权限</Button>
          )}
          {can('role:write') && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          )}
          {can('role:delete') && (
            <Popconfirm title="确认删除该角色？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger disabled={record.is_builtin}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} className="page-title">角色管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('role:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建角色</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        pagination={false}
      />

      <Modal
        title={editing ? '编辑角色' : '新建角色'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="角色名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入编码' }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`配置权限 - ${permRole?.name ?? ''} ${permRole?.is_builtin ? '(内置角色)' : ''}`}
        open={!!permRole}
        onOk={submitPermissions}
        onCancel={() => setPermRole(null)}
        width={680}
        okButtonProps={{ disabled: permRole?.code === 'super-admin' }}
        destroyOnClose
      >
        {permRole?.code === 'super-admin' && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="超级管理员默认拥有系统全部权限（通配 * ），不可修改权限集合。"
          />
        )}
        <Tree
          checkable
          defaultExpandAll
          disabled={permRole?.code === 'super-admin'}
          checkedKeys={checkedKeys}
          onCheck={(keys) => {
            const list = Array.isArray(keys) ? keys : (keys as { checked: (string | number)[] }).checked
            setCheckedKeys(list.map(String))
          }}
          treeData={buildPermissionTree(permissions)}
        />
      </Modal>
    </div>
  )
}