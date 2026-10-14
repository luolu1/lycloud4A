import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Dropdown,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { MenuProps } from 'antd'
import { PlusOutlined, ReloadOutlined, ApiOutlined, LinkOutlined } from '@ant-design/icons'
import { appApi, toolApi } from '../../api/endpoints'
import { callConnectAgent, extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { ApplicationOut, LaunchToolOut } from '../../types'
import { formatDateTime } from '../../utils/format'

const { Title } = Typography

const AGENT_URL = 'http://127.0.0.1:47621'

const typeLabels: Record<string, string> = {
  network: '网络设备',
  security: '安全设备',
  server: '服务器',
  database: '数据库',
  middleware: '中间件',
  bastion: '堡垒机',
  web: 'Web 应用',
  infra: '其它基础设施',
}

const typeColors: Record<string, string> = {
  network: 'blue',
  security: 'red',
  server: 'green',
  database: 'purple',
  middleware: 'cyan',
  bastion: 'gold',
  web: 'geekblue',
  infra: 'default',
}

const connStatusMeta: Record<string, { color: string; label: string }> = {
  online: { color: 'green', label: '在线' },
  offline: { color: 'red', label: '离线' },
  unreachable: { color: 'orange', label: '无法探测' },
  unknown: { color: 'default', label: '未检测' },
}

const protocolOptions = [
  'ssh', 'telnet', 'rdp', 'vnc', 'sftp', 'ftp', 'serial',
  'tacacs', 'radius', 'ldap', 'http', 'https', 'oidc', 'saml', 'local',
]

export default function AppsPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<ApplicationOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [checkingId, setCheckingId] = useState<number | null>(null)
  const [connectingId, setConnectingId] = useState<number | null>(null)
  const [tools, setTools] = useState<LaunchToolOut[]>([])
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<ApplicationOut | null>(null)
  const [form] = Form.useForm()
  const credentialType = Form.useWatch('credential_type', form)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await appApi.list({ page, page_size: pageSize, q: q || undefined })
      setData(resp.items)
      setTotal(resp.total)
    } catch (err) {
      message.error(extractError(err, '加载设备失败'))
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
        setTools(await toolApi.list())
      } catch {
        setTools([])
      }
    })()
  }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ app_type: 'server', protocol: 'ssh', credential_type: 'password', status: true })
    setEditOpen(true)
  }

  const openEdit = (record: ApplicationOut) => {
    setEditing(record)
    form.setFieldsValue({ ...record, credential: undefined })
    setEditOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await appApi.update(editing.id, values)
        message.success('设备已更新')
      } else {
        await appApi.create(values)
        message.success('设备已纳管，已完成首次连通性探测')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: ApplicationOut) => {
    try {
      await appApi.remove(record.id)
      message.success('设备已移除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const check = async (record: ApplicationOut) => {
    setCheckingId(record.id)
    try {
      const result = await appApi.check(record.id)
      const meta = connStatusMeta[result.conn_status] ?? connStatusMeta.unknown
      if (result.conn_status === 'online') {
        message.success(`${record.name}：${meta.label}`)
      } else {
        message.warning(`${record.name}：${meta.label}${result.error ? ` - ${result.error}` : ''}`)
      }
      await load()
    } catch (err) {
      message.error(extractError(err, '检测失败'))
    } finally {
      setCheckingId(null)
    }
  }

  const connect = async (record: ApplicationOut, tool: LaunchToolOut) => {
    setConnectingId(record.id)
    try {
      const browserHost = window.location.hostname
      const res = await appApi.connect(record.id, tool.id, AGENT_URL, browserHost)
      const launched = await callConnectAgent(res.agent_url, res.ticket)
      message.success(`正在用 ${launched.tool || tool.name} 连接 ${launched.device || record.name}`)
    } catch (err) {
      if (err instanceof TypeError) {
        message.error('无法连接本地助手：请先下载并运行 lycloud4A 连接助手（连接工具页可下载）')
      } else {
        message.error(extractError(err, '发起连接失败'))
      }
    } finally {
      setConnectingId(null)
    }
  }

  const connectMenu = (record: ApplicationOut): MenuProps => ({
    items: tools
      .filter((t) => {
        if (!t.status) return false
        const supported = (t.protocols || "").split(",").map((item) => item.trim().toLowerCase())
        return supported.includes(record.protocol.toLowerCase())
      })
      .map((t) => ({ key: String(t.id), label: `${t.name}（${t.exe_path.split(/[\\/]/).pop()}）` })),
    onClick: ({ key }) => {
      const tool = tools.find((t) => String(t.id) === key)
      if (tool) void connect(record, tool)
    },
  })

  const compatibleToolCount = (record: ApplicationOut) => tools.filter((tool) => {
    if (!tool.status) return false
    return (tool.protocols || "").split(",").map((item) => item.trim().toLowerCase())
      .includes(record.protocol.toLowerCase())
  }).length

  const columns: ColumnsType<ApplicationOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '类型',
      dataIndex: 'app_type',
      width: 110,
      render: (v: string) => <Tag color={typeColors[v] || 'default'}>{typeLabels[v] || v}</Tag>,
    },
    {
      title: '认证协议',
      dataIndex: 'protocol',
      width: 100,
      render: (v: string) => <Tag>{(v || '').toUpperCase()}</Tag>,
    },
    { title: '地址/网段', dataIndex: 'url', render: (v) => v || '-' },
    { title: '登录用户', dataIndex: 'login_username', width: 100, render: (v) => v || '-' },
    {
      title: '凭证',
      dataIndex: 'has_credential',
      width: 90,
      render: (v: boolean, record) =>
        v ? (
          <Tag color="blue">{record.credential_type === 'ssh_key' ? 'SSH 密钥' : '密码'}</Tag>
        ) : (
          <Tag>未配置</Tag>
        ),
    },
    { title: '负责人', dataIndex: 'owner', width: 100, render: (v) => v || '-' },
    {
      title: '连接状态',
      dataIndex: 'conn_status',
      width: 110,
      render: (v: string, record) => {
        const meta = connStatusMeta[v] ?? connStatusMeta.unknown
        const tag = <Tag color={meta.color}>{meta.label}</Tag>
        if (v === 'offline' || v === 'unreachable') {
          return (
            <Tooltip title={`${record.last_check_error || ''}${record.last_checked_at ? `（${formatDateTime(record.last_checked_at)}）` : ''}`}>
              {tag}
            </Tooltip>
          )
        }
        return record.last_checked_at ? (
          <Tooltip title={`最近检测：${formatDateTime(record.last_checked_at)}`}>{tag}</Tooltip>
        ) : (
          tag
        )
      },
    },
    {
      title: '启用',
      dataIndex: 'status',
      width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      width: 280,
      fixed: 'right',
      render: (_v, record) => (
        <Space size="small">
          <Dropdown
            menu={connectMenu(record)}
            disabled={compatibleToolCount(record) === 0}
            trigger={['click']}
          >
            <Button
              type="link"
              size="small"
              icon={<LinkOutlined />}
              loading={connectingId === record.id}
            >
              连接
            </Button>
          </Dropdown>
          <Button
            type="link"
            size="small"
            icon={<ApiOutlined />}
            loading={checkingId === record.id}
            onClick={() => void check(record)}
          >
            检测
          </Button>
          {can('application:write') && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          )}
          {can('application:delete') && (
            <Popconfirm title="确认移除该设备？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} className="page-title">设备管理</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索名称/编码"
          style={{ width: 260 }}
          onSearch={(value) => { setPage(1); setQ(value) }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('application:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>纳管设备</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        scroll={{ x: 1300 }}
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
        title={editing ? '编辑设备' : '纳管设备'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如：核心交换机集群" />
          </Form.Item>
          <Form.Item name="app_type" label="设备类型" rules={[{ required: true }]}>
            <Select
              options={Object.entries(typeLabels).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="protocol" label="认证协议" rules={[{ required: true }]}>
            <Select
              options={protocolOptions.map((v) => ({ value: v, label: v.toUpperCase() }))}
            />
          </Form.Item>
          <Form.Item name="url" label="地址 / 网段 / URL">
            <Input placeholder="终端类：10.0.1.1 或 10.0.1.1:22；Web 应用：http://10.0.0.60:8080/" />
          </Form.Item>
          <Form.Item name="login_username" label="登录用户"><Input placeholder="如：root / netadmin" /></Form.Item>
          <Form.Item name="credential_type" label="凭证类型" initialValue="password">
            <Select
              options={[
                { value: 'password', label: '登录密码' },
                { value: 'ssh_key', label: 'SSH 私钥' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="credential"
            label={credentialType === 'ssh_key' ? 'SSH 私钥' : '登录密码'}
            extra={editing ? '留空则保持原凭证不变' : '加密存储，列表仅显示是否已配置'}
          >
            {credentialType === 'ssh_key' ? (
              <Input.TextArea rows={4} placeholder="粘贴 PEM 私钥内容" />
            ) : (
              <Input.Password placeholder="设备登录密码" />
            )}
          </Form.Item>
          <Form.Item name="owner" label="负责人 / 团队"><Input placeholder="如：运维中心" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="status" label="启用" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
