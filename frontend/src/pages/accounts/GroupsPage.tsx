import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { groupApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { GroupOut } from '../../types'

const { Title } = Typography

export default function GroupsPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<GroupOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<GroupOut | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await groupApi.list({ page, page_size: pageSize, q: q || undefined })
      setData(resp.items)
      setTotal(resp.total)
    } catch (err) {
      message.error(extractError(err, '加载用户组失败'))
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, q, message])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setEditOpen(true)
  }

  const openEdit = (record: GroupOut) => {
    setEditing(record)
    form.setFieldsValue(record)
    setEditOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await groupApi.update(editing.id, values)
        message.success('用户组已更新')
      } else {
        await groupApi.create(values)
        message.success('用户组已创建')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: GroupOut) => {
    try {
      await groupApi.remove(record.id)
      message.success('用户组已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const columns: ColumnsType<GroupOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    { title: '编码', dataIndex: 'code' },
    { title: '描述', dataIndex: 'description', render: (v) => v || '-' },
    { title: '成员数', dataIndex: 'member_count', width: 90 },
    {
      title: '操作',
      width: 160,
      render: (_v, record) => (
        <Space size="small">
          {can('group:write') && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          )}
          {can('group:delete') && (
            <Popconfirm title="确认删除该用户组？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} className="page-title">用户组管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索名称/编码"
          style={{ width: 260 }}
          onSearch={(value) => { setPage(1); setQ(value) }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('group:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建用户组</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
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
        title={editing ? '编辑用户组' : '新建用户组'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入编码' }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}