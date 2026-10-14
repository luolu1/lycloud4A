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
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DownloadOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { toolApi } from '../../api/endpoints'
import { detectAgentTool, extractError, fetchAgentHealth } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { LaunchToolOut } from '../../types'

const { Title, Paragraph, Text } = Typography

const AGENT_URL = 'http://127.0.0.1:47621'

// 连接助手最低版本：低于此版本可能缺少某些协议的会话日志能力（如 MobaXterm 的 sftp/ftp）。
const AGENT_MIN_VERSION = '1.0.9'

const versionLt = (a: string, b: string): boolean => {
  const pa = String(a || '').split('.').map((n) => parseInt(n, 10) || 0)
  const pb = String(b || '').split('.').map((n) => parseInt(n, 10) || 0)
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const x = pa[i] || 0
    const y = pb[i] || 0
    if (x !== y) return x < y
  }
  return false
}

const KIND_OPTIONS = [
  { value: 'mobaxterm', label: 'MobaXterm', default: 'C:\\Program Files (x86)\\Mobatek\\MobaXterm\\MobaXterm.exe' },
  { value: 'netcatty', label: 'NetCatty', default: 'C:\\Program Files\\NetCatty\\NetCatty.exe' },
  { value: 'xshell', label: 'Xshell', default: 'C:\\Program Files\\NetSarang\\Xshell 7\\Xshell.exe' },
  { value: 'securecrt', label: 'SecureCRT', default: 'C:\\Program Files\\VanDyke Software\\SecureCRT\\SecureCRT.exe' },
  { value: 'winscp', label: 'WinSCP', default: 'C:\\Program Files (x86)\\WinSCP\\WinSCP.exe' },
  { value: 'chrome', label: 'Chrome', default: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' },
]

type DetectState = 'installed' | 'missing' | 'checking'

export default function ToolsPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<LaunchToolOut[]>([])
  const [loading, setLoading] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<LaunchToolOut | null>(null)
  const [detect, setDetect] = useState<Record<number, DetectState>>({})
  const [agentVersion, setAgentVersion] = useState<string | null>(null)
  const [agentAvailable, setAgentAvailable] = useState<boolean | null>(null)
  const [form] = Form.useForm()

  const checkAgent = useCallback(async () => {
    try {
      const res = await fetchAgentHealth(AGENT_URL)
      setAgentVersion(res.version)
      setAgentAvailable(true)
    } catch {
      setAgentVersion(null)
      setAgentAvailable(false)
    }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await toolApi.list())
    } catch (err) {
      message.error(extractError(err, '加载连接工具失败'))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
    void checkAgent()
  }, [load, checkAgent])

  const existingKinds = data.map((t) => t.kind)
  const availableKinds = KIND_OPTIONS.filter((k) => !existingKinds.includes(k.value))

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    const first = availableKinds[0]
    if (first) form.setFieldsValue({ kind: first.value, exe_path: first.default, status: true })
    setEditOpen(true)
  }

  const openEdit = (record: LaunchToolOut) => {
    setEditing(record)
    form.setFieldsValue(record)
    setEditOpen(true)
  }

  const onKindChange = (value: string) => {
    const opt = KIND_OPTIONS.find((k) => k.value === value)
    if (opt && !editing) form.setFieldsValue({ exe_path: opt.default })
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await toolApi.update(editing.id, { exe_path: values.exe_path, status: values.status })
        message.success('连接工具已更新')
      } else {
        await toolApi.create(values)
        message.success('连接工具已新增')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: LaunchToolOut) => {
    try {
      await toolApi.remove(record.id)
      message.success('连接工具已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const checkInstalled = async (record: LaunchToolOut) => {
    setDetect((s) => ({ ...s, [record.id]: 'checking' }))
    try {
      const res = await detectAgentTool(AGENT_URL, record.exe_path)
      setDetect((s) => ({ ...s, [record.id]: res.installed ? 'installed' : 'missing' }))
      if (res.installed) {
        message.success(`${record.name} 已安装`)
      } else {
        message.warning(`${record.name} 未检测到，请确认路径：${record.exe_path}`)
      }
    } catch {
      setDetect((s) => {
        const next = { ...s }
        delete next[record.id]
        return next
      })
      message.error('无法连接本地助手：请先下载并运行 lycloud4A 连接助手')
    }
  }

  const download = () => {
    // 附带版本号，避免浏览器命中旧安装包的缓存
    window.open(`/api/v1/client/download?v=${AGENT_MIN_VERSION}`, '_blank')
  }

  const columns: ColumnsType<LaunchToolOut> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '软件', dataIndex: 'name', width: 140 },
    { title: '程序路径', dataIndex: 'exe_path', render: (v) => <Text code>{v}</Text> },
    {
      title: '支持协议',
      dataIndex: 'protocols',
      width: 220,
      render: (v: string | null) =>
        v ? v.split(',').map((p) => <Tag key={p}>{p.trim().toUpperCase()}</Tag>) : '-',
    },
    {
      title: '安装状态',
      key: 'detect',
      width: 110,
      render: (_v, record) => {
        const st = detect[record.id]
        if (st === 'installed') return <Tag icon={<CheckCircleOutlined />} color="green">已安装</Tag>
        if (st === 'missing') return <Tag icon={<CloseCircleOutlined />} color="red">未安装</Tag>
        if (st === 'checking') return <Tag color="processing">检测中</Tag>
        return <Tag>未检测</Tag>
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
      width: 200,
      render: (_v, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<SearchOutlined />} onClick={() => void checkInstalled(record)}>
            检测
          </Button>
          {can('application:write') && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          )}
          {can('application:write') && (
            <Popconfirm title="确认删除该连接工具？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} className="page-title">连接工具</Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="下载并安装 lycloud4A 连接助手后，在设备管理页点击“连接”即可一键调起对应软件并自动登录"
        description={
          <Paragraph style={{ marginBottom: 0 }}>
            连接助手是一个 Windows 安装程序（<Text code>lycloud4A-Setup.exe</Text>），安装后随开机在后台
            常驻运行（无需保留窗口），负责在你的电脑上启动 MobaXterm / NetCatty / Xshell / SecureCRT /
            Chrome 等软件并自动代入设备凭证。安装后可用下方“检测”按钮确认各软件是否正常。
          </Paragraph>
        }
      />
      <Space style={{ marginBottom: 16 }} wrap>
        <Button type="primary" icon={<DownloadOutlined />} onClick={download}>
          下载连接助手安装包
        </Button>
        <Button icon={<ReloadOutlined />} onClick={() => { void load(); void checkAgent() }}>刷新</Button>
        {can('application:write') && availableKinds.length > 0 && (
          <Button icon={<PlusOutlined />} onClick={openCreate}>新增工具</Button>
        )}
      </Space>
      {agentAvailable === true && (
        <div style={{ marginBottom: 12 }}>
          <Tag color={agentVersion && versionLt(agentVersion, AGENT_MIN_VERSION) ? 'orange' : 'green'}>
            本地连接助手 v{agentVersion}
          </Tag>
          {agentVersion && versionLt(agentVersion, AGENT_MIN_VERSION) && (
            <Text type="warning">
              版本过旧（建议 v{AGENT_MIN_VERSION} 及以上）：旧版本可能无法记录 MobaXterm 的
              sftp/ftp 会话日志，且 sftp 会话会被当成 ssh 终端打开，请点击上方按钮重新下载安装。
            </Text>
          )}
        </div>
      )}
      {agentAvailable === false && (
        <div style={{ marginBottom: 12 }}>
          <Tag>本地连接助手未运行</Tag>
          <Text type="secondary">未检测到 127.0.0.1:47621，请先下载并运行 lycloud4A 连接助手。</Text>
        </div>
      )}
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        scroll={{ x: 1100 }}
        pagination={false}
      />

      <Modal
        title={editing ? `编辑连接工具 - ${editing.name}` : '新增连接工具'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="kind" label="软件" rules={[{ required: true, message: '请选择软件' }]}>
            <Select
              disabled={!!editing}
              onChange={onKindChange}
              options={(editing ? KIND_OPTIONS : availableKinds).map((k) => ({
                value: k.value,
                label: k.label,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="exe_path"
            label="程序路径"
            rules={[{ required: true, message: '请输入可执行程序路径' }]}
          >
            <Input placeholder="如：D:\\movaxterm\\install\\MobaXterm.exe" />
          </Form.Item>
          <Form.Item name="status" label="启用" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
