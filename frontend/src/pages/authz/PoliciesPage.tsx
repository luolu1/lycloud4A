import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { policyApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { PolicyOut } from '../../types'

const { Title } = Typography

export default function PoliciesPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<PolicyOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<PolicyOut | null>(null)
  const [form] = Form.useForm()

  const [evalOpen, setEvalOpen] = useState(false)
  const [evalForm] = Form.useForm()
  const [evalResult, setEvalResult] = useState<{ allowed: boolean; matched_policy: string | null; reason: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await policyApi.list({ page, page_size: pageSize, q: q || undefined })
      setData(resp.items)
      setTotal(resp.total)
    } catch (err) {
      message.error(extractError(err, '加载策略失败'))
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
    form.setFieldsValue({
      effect: 'allow',
      priority: 100,
      subject_type: 'user',
      resource_type: 'application',
      actions: [],
      conditions: {},
      enabled: true,
    })
    setEditOpen(true)
  }

  const openEdit = (record: PolicyOut) => {
    setEditing(record)
    form.setFieldsValue({
      ...record,
      conditions: record.conditions ? JSON.stringify(record.conditions) : '{}',
      actions: record.actions.join(','),
    })
    setEditOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    const actions = typeof values.actions === 'string'
      ? values.actions.split(',').map((s: string) => s.trim()).filter(Boolean)
      : values.actions
    let conditions: Record<string, unknown> = {}
    if (values.conditions) {
      try {
        conditions = JSON.parse(values.conditions)
      } catch {
        message.error('conditions 必须是合法 JSON')
        return
      }
    }
    const payload = { ...values, actions, conditions }
    try {
      if (editing) {
        await policyApi.update(editing.id, payload)
        message.success('策略已更新')
      } else {
        await policyApi.create(payload)
        message.success('策略已创建')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: PolicyOut) => {
    try {
      await policyApi.remove(record.id)
      message.success('策略已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const runEvaluate = async () => {
    const values = await evalForm.validateFields()
    try {
      setEvalResult(await policyApi.evaluate(values))
    } catch (err) {
      message.error(extractError(err, '求值失败'))
    }
  }

  const columns: ColumnsType<PolicyOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '效果',
      dataIndex: 'effect',
      width: 90,
      render: (v: string) => <Tag color={v === 'allow' ? 'green' : 'red'}>{v}</Tag>,
    },
    { title: '优先级', dataIndex: 'priority', width: 90 },
    { title: '主体', dataIndex: 'subject_type', width: 90 },
    { title: '主体ID', dataIndex: 'subject_id', width: 90, render: (v) => v ?? '所有' },
    {
      title: '动作',
      dataIndex: 'actions',
      render: (v: string[]) => (Array.isArray(v) ? v.map((a) => <Tag key={a}>{a}</Tag>) : '-'),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 80,
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : <Tag>否</Tag>),
    },
    {
      title: '操作',
      width: 180,
      render: (_v, record) => (
        <Space size="small">
          {can('policy:write') && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          )}
          {can('policy:delete') && (
            <Popconfirm title="确认删除该策略？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4}>访问策略（ABAC）</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索策略名称"
          style={{ width: 260 }}
          onSearch={(value) => { setPage(1); setQ(value) }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('policy:read') && (
          <Button onClick={() => { setEvalOpen(true); setEvalResult(null); evalForm.resetFields() }}>
            访问求值测试
          </Button>
        )}
        {can('policy:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建策略</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        scroll={{ x: 1100 }}
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
        title={editing ? '编辑策略' : '新建策略'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="策略名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
          <Space.Compact block>
            <Form.Item name="effect" label="效果" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={[{ value: 'allow', label: '允许 allow' }, { value: 'deny', label: '拒绝 deny' }]} />
            </Form.Item>
            <Form.Item name="priority" label="优先级（小者优先）" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={1} max={9999} style={{ width: '100%' }} />
            </Form.Item>
          </Space.Compact>
          <Space.Compact block>
            <Form.Item name="subject_type" label="主体类型" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={['user', 'group', 'role', 'org'].map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="subject_id" label="主体ID（留空=所有）" style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Space.Compact>
          <Space.Compact block>
            <Form.Item name="resource_type" label="资源类型" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={['application', 'secret', 'server'].map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="resource_id" label="资源ID（留空=所有）" style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Space.Compact>
          <Form.Item
            name="actions"
            label="动作（逗号分隔，如 launch,read）"
            rules={[{ required: true, message: '请输入动作' }]}
          >
            <Input placeholder="launch,read" />
          </Form.Item>
          <Form.Item name="conditions" label="条件（JSON，可选）">
            <Input.TextArea rows={3} placeholder='{"time_range": {"start": "09:00", "end": "18:00"}}' />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="访问求值测试"
        open={evalOpen}
        onCancel={() => setEvalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={evalForm} layout="vertical" initialValues={{ subject_type: 'user', resource_type: 'application' }}>
          <Space.Compact block>
            <Form.Item name="subject_type" label="主体类型" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={['user', 'group', 'role', 'org'].map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="subject_id" label="主体ID" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Space.Compact>
          <Space.Compact block>
            <Form.Item name="resource_type" label="资源类型" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={['application', 'secret', 'server'].map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="resource_id" label="资源ID" style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Space.Compact>
          <Form.Item name="action" label="动作" rules={[{ required: true, message: '请输入动作' }]}>
            <Input placeholder="launch" />
          </Form.Item>
          <Button type="primary" onClick={() => void runEvaluate()} block>
            开始求值
          </Button>
        </Form>
        {evalResult && (
          <Alert
            style={{ marginTop: 16 }}
            type={evalResult.allowed ? 'success' : 'error'}
            message={evalResult.allowed ? '允许访问' : '拒绝访问'}
            description={`命中策略：${evalResult.matched_policy || '无'}；原因：${evalResult.reason}`}
          />
        )}
      </Modal>
    </div>
  )
}