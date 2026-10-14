import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Descriptions,
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
import { EyeOutlined, KeyOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { secretApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { SecretOut, SecretValueOut, SecretVersionOut } from '../../types'
import { formatDateTime } from '../../utils/format'

const { Title } = Typography

const categoryLabels: Record<string, string> = {
  app: '应用密码',
  database: '数据库',
  middleware: '中间件',
  infrastructure: '基础设施',
  api_token: 'API 令牌',
}

export default function SecretsPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<SecretOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<SecretOut | null>(null)
  const [form] = Form.useForm()
  const rotationEnabled = Form.useWatch('rotation_enabled', form)

  const [valueSecret, setValueSecret] = useState<SecretOut | null>(null)
  const [valueData, setValueData] = useState<SecretValueOut | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [versions, setVersions] = useState<SecretVersionOut[]>([])

  const [editValueSecret, setEditValueSecret] = useState<SecretOut | null>(null)
  const [valueForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await secretApi.list({ page, page_size: pageSize, q: q || undefined })
      setData(resp.items)
      setTotal(resp.total)
    } catch (err) {
      message.error(extractError(err, '加载密钥失败'))
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
      category: 'app',
      rotation_enabled: false,
      rotation_type: 'manual',
      rotation_interval_days: 30,
      tags: '',
    })
    setEditOpen(true)
  }

  const openEdit = (record: SecretOut) => {
    setEditing(record)
    form.setFieldsValue(record)
    setEditOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await secretApi.update(editing.id, values)
        message.success('密钥已更新')
      } else {
        const { data: secretData, tags, ...rest } = values
        const tagsDict: Record<string, string> = {}
        if (typeof tags === 'string') {
          for (const pair of tags.split(',')) {
            const idx = pair.indexOf('=')
            const key = (idx > 0 ? pair.slice(0, idx) : pair).trim()
            if (key) tagsDict[key] = idx > 0 ? pair.slice(idx + 1).trim() : ''
          }
        } else if (tags && typeof tags === 'object') {
          Object.assign(tagsDict, tags)
        }
        await secretApi.create({ ...rest, tags: tagsDict, data: secretData || {} })
        message.success('密钥已创建')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: SecretOut) => {
    try {
      await secretApi.remove(record.id)
      message.success('密钥已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const viewValue = async (record: SecretOut) => {
    try {
      const [value, vers] = await Promise.all([secretApi.value(record.id), secretApi.versions(record.id)])
      setValueSecret(record)
      setValueData(value)
      setRevealed(false)
      setVersions(vers)
    } catch (err) {
      message.error(extractError(err, '读取失败'))
    }
  }

  const reveal = async () => {
    if (!valueSecret) return
    try {
      const value = await secretApi.value(valueSecret.id, { reveal: true })
      setValueData(value)
      setRevealed(true)
    } catch (err) {
      message.error(extractError(err, '无权限读取明文'))
    }
  }

  const rotate = async (record: SecretOut) => {
    try {
      const result = await secretApi.rotate(record.id)
      if (result.success) {
        message.success(`轮换成功：新版本 v${result.new_version}`)
      } else {
        message.warning(`轮换未生成新版本：${result.message}`)
      }
      await load()
    } catch (err) {
      message.error(extractError(err, '轮换失败'))
    }
  }

  const submitValue = async () => {
    if (!editValueSecret) return
    const values = await valueForm.validateFields()
    const dataMap: Record<string, string> = {}
    for (const line of (values.dataText as string).split('\n')) {
      const idx = line.indexOf('=')
      if (idx > 0) dataMap[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
    }
    try {
      await secretApi.setValue(editValueSecret.id, { data: dataMap, comment: values.comment })
      message.success('新版本已写入')
      setEditValueSecret(null)
      await load()
    } catch (err) {
      message.error(extractError(err, '写入失败'))
    }
  }

  const columns: ColumnsType<SecretOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '类型',
      dataIndex: 'category',
      width: 110,
      render: (v: string) => <Tag>{categoryLabels[v] || v}</Tag>,
    },
    { title: '路径', dataIndex: 'path', width: 200 },
    { title: '版本', dataIndex: 'current_version', width: 80 },
    {
      title: '自动轮换',
      dataIndex: 'rotation_enabled',
      width: 100,
      render: (v: boolean) => (v ? <Tag color="green">开启</Tag> : <Tag>关闭</Tag>),
    },
    { title: '下次轮换', dataIndex: 'next_rotation_at', width: 160, render: (v) => formatDateTime(v) },
    { title: '最近轮换', dataIndex: 'last_rotated_at', width: 160, render: (v) => formatDateTime(v) },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: boolean) => (v ? <Tag color="green">可用</Tag> : <Tag color="red">停用</Tag>),
    },
    {
      title: '操作',
      width: 320,
      fixed: 'right',
      render: (_v, record) => (
        <Space size="small" wrap>
          {can('secret:read') && <Button type="link" size="small" onClick={() => void viewValue(record)}>查看</Button>}
          {can('secret:write') && (
            <Button type="link" size="small" onClick={() => { setEditValueSecret(record); valueForm.resetFields() }}>
              写新版本
            </Button>
          )}
          {can('secret:write') && <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>}
          {can('secret:rotate') && (
            <Button type="link" size="small" onClick={() => void rotate(record)} icon={<KeyOutlined />}>
              轮换
            </Button>
          )}
          {can('secret:delete') && (
            <Popconfirm title="确认删除该密钥？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  const versionOf = (key: string): string => {
    if (!valueData) return '-'
    const source = revealed ? valueData.data : valueData.masked
    return source?.[key] ?? '(已删除字段)'
  }

  return (
    <div>
      <Title level={4} className="page-title">密码托管</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索名称/路径"
          style={{ width: 260 }}
          onSearch={(value) => { setPage(1); setQ(value) }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('secret:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>托管新密钥</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        scroll={{ x: 1400 }}
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
        title={editing ? '编辑密钥' : '托管新密钥'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="category" label="类型" rules={[{ required: true }]}>
            <Select options={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item name="path" label="路径（唯一标识）" rules={[{ required: true, message: '请输入路径' }]}>
            <Input placeholder="app/prod/mysql-root" disabled={!!editing} />
          </Form.Item>
          {!editing && (
            <>
              <Form.Item name="data" label="初始字段（key=value，每行一个）">
                <Input.TextArea rows={5} placeholder={'password=YourStrongPass!\nusername=root'} />
              </Form.Item>
              <Form.Item name="tags" label="标签（k=v，逗号分隔）">
                <Input placeholder="env=prod,team=ops" />
              </Form.Item>
            </>
          )}
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="owner" label="负责人"><Input /></Form.Item>
          <Form.Item name="rotation_enabled" label="启用自动轮换" valuePropName="checked">
            <Switch />
          </Form.Item>
          {rotationEnabled && (
            <Space.Compact block>
              <Form.Item name="rotation_type" label="轮换方式" rules={[{ required: true }]} style={{ flex: 1 }}>
                <Select
                  options={['manual', 'mysql', 'postgres', 'redis', 'ssh_local', 'api'].map((v) => ({
                    value: v,
                    label: v,
                  }))}
                />
              </Form.Item>
              <Form.Item name="rotation_interval_days" label="轮换周期(天)" rules={[{ required: true }]} style={{ flex: 1 }}>
                <InputNumber min={1} max={3650} style={{ width: '100%' }} />
              </Form.Item>
            </Space.Compact>
          )}
          <Form.Item name="rotate_target" label="轮换目标主机/IP"><Input /></Form.Item>
          <Form.Item name="rotate_username" label="轮换账号"><Input /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`密钥详情 - ${valueSecret?.name ?? ''}`}
        open={!!valueSecret}
        onCancel={() => setValueSecret(null)}
        width={640}
        footer={
          <Space>
            {can('secret:reveal') && !revealed && (
              <Button type="primary" icon={<EyeOutlined />} onClick={() => void reveal()}>
                显示明文
              </Button>
            )}
            <Button onClick={() => setValueSecret(null)}>关闭</Button>
          </Space>
        }
        destroyOnClose
      >
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="路径">{valueSecret?.path}</Descriptions.Item>
          <Descriptions.Item label="当前版本">v{valueData?.version}</Descriptions.Item>
          {(valueData ? Object.keys(revealed ? valueData.data : valueData.masked) : []).map((key) => (
            <Descriptions.Item key={key} label={key}>
              <Typography.Text code>{versionOf(key)}</Typography.Text>
            </Descriptions.Item>
          ))}
        </Descriptions>
        <Typography.Title level={5} style={{ marginTop: 16 }}>版本历史</Typography.Title>
        <Table
          size="small"
          rowKey="version"
          pagination={false}
          dataSource={versions}
          columns={[
            { title: '版本', dataIndex: 'version', width: 80, render: (v) => <Tag>v{v}</Tag> },
            { title: '写入时间', dataIndex: 'created_at', render: (v) => formatDateTime(v) },
            { title: '操作者', dataIndex: 'created_by', render: (v) => v || '-' },
            { title: '说明', dataIndex: 'comment', render: (v) => v || '-' },
          ]}
        />
      </Modal>

      <Modal
        title={`写入新版本 - ${editValueSecret?.name ?? ''}`}
        open={!!editValueSecret}
        onOk={submitValue}
        onCancel={() => setEditValueSecret(null)}
        destroyOnClose
      >
        <Form form={valueForm} layout="vertical">
          <Form.Item name="dataText" label="字段（key=value，每行一个）" rules={[{ required: true, message: '请输入字段' }]}>
            <Input.TextArea rows={6} placeholder={'password=NewPass123!\nusername=root'} />
          </Form.Item>
          <Form.Item name="comment" label="变更说明"><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}