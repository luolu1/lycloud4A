import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  DatePicker,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { auditApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import type { AuditOut } from '../../types'
import { formatDateTime } from '../../utils/format'

const { Title } = Typography
const { RangePicker } = DatePicker

const categoryLabels: Record<string, string> = {
  auth: '认证',
  account: '账号',
  authz: '授权',
  admin: '管理',
  vault: '密码托管',
  connection: '连接设备',
}

const actionLabels: Record<string, string> = {
  "连接设备": "连接设备",
  "解析连接凭证": "解析连接凭证",
  "纳管设备": "纳管设备",
  "更新设备": "更新设备",
  "移除设备": "移除设备",
  "检测设备连接": "检测设备连接",
  device_check: "检测设备连接",
  app_create: "纳管设备",
  app_update: "更新设备",
  app_delete: "移除设备",
  login: "登录",
  login_failed: "登录失败",
  logout: "退出登录",
  user_create: "创建用户",
  user_update: "更新用户",
  user_delete: "删除用户",
  tool_create: "新增连接工具",
  tool_update: "更新连接工具",
  tool_delete: "删除连接工具",
}

const typeLabels: Record<string, string> = {
  network: "网络设备",
  security: "安全设备",
  server: "服务器",
  database: "数据库",
  middleware: "中间件",
  bastion: "堡垒机",
  web: "Web 应用",
}

export default function AuditPage() {
  const { message } = App.useApp()
  const [data, setData] = useState<AuditOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [category, setCategory] = useState<string | undefined>()
  const [result, setResult] = useState<string | undefined>()
  const [actor, setActor] = useState('')
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [loading, setLoading] = useState(false)
  const [logModalOpen, setLogModalOpen] = useState(false)
  const [activeLog, setActiveLog] = useState<{ path: string | null; content: string | null; error: string | null; title: string }>({
    path: null,
    content: null,
    error: null,
    title: '',
  })

  const viewLog = async (record: AuditOut) => {
    try {
      const data = await auditApi.logContent(record.id)
      setActiveLog({
        path: data.path,
        content: data.content,
        error: data.error,
        title: `会话操作日志 - ${record.target_name || record.action} (${record.actor_username || 'system'})`,
      })
      setLogModalOpen(true)
    } catch (err) {
      message.error(extractError(err, '读取日志内容失败'))
    }
  }

  const search = useCallback(async (p = page, ps = pageSize) => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page: p, page_size: ps }
      if (category) params.category = category
      if (result) params.result = result
      if (actor) params.actor_username = actor
      if (range?.[0]) params.start = range[0].startOf('day').toISOString()
      if (range?.[1]) params.end = range[1].endOf('day').toISOString()
      const resp = await auditApi.list(params)
      setData(resp.items)
      setTotal(resp.total)
    } catch (err) {
      message.error(extractError(err, '加载审计日志失败'))
    } finally {
      setLoading(false)
    }
  }, [category, result, actor, range, message])

  useEffect(() => {
    void search()
  }, [search])

  const columns: ColumnsType<AuditOut> = [
    { title: '时间', dataIndex: 'timestamp', width: 180, render: (v) => formatDateTime(v) },
    {
      title: '类别',
      dataIndex: 'category',
      width: 100,
      render: (v: string) => <Tag color="blue">{categoryLabels[v] || v}</Tag>,
    },
    { title: '动作', dataIndex: 'action', width: 140, render: (v: string) => actionLabels[v] || v },
    {
      title: '结果',
      dataIndex: 'result',
      width: 90,
      render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v === 'success' ? '成功' : '失败'}</Tag>,
    },
    { title: '操作者', dataIndex: 'actor_username', width: 120, render: (v) => v || 'system' },
    { title: '目标设备', dataIndex: 'target_name', width: 180, render: (v) => v || '-' },
    {
      title: '设备类型',
      width: 120,
      render: (_v, r) => {
        const val = r.device_type || (r.detail && typeof r.detail === 'object' ? (r.detail['设备类型'] as string | undefined) : undefined)
        return val ? (typeLabels[val] || val) : '-'
      },
    },
    {
      title: '连接工具',
      width: 130,
      render: (_v, r) => {
        const val = r.connect_tool || (r.detail && typeof r.detail === 'object' ? (r.detail['连接工具'] as string | undefined) : undefined)
        return val || '-'
      },
    },
    { title: '访问IP', dataIndex: 'actor_ip', width: 130, render: (v) => v || '-' },
    {
      title: '信息',
      dataIndex: 'message',
      render: (v, r) => {
        const hasLog = r.has_log_content || !!r.log_file_path || !!(r.detail && typeof r.detail === 'object' && r.detail['日志文件路径'])
        if (hasLog) {
          return (
            <Button
              type="link"
              size="small"
              icon={<FileTextOutlined />}
              style={{ padding: 0 }}
              onClick={() => void viewLog(r)}
            >
              查看操作日志
            </Button>
          )
        }
        return v || '-'
      },
    },
  ]

  return (
    <div>
      <Title level={4} className="page-title">审计日志</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="类别"
          style={{ width: 140 }}
          value={category}
          onChange={setCategory}
          options={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))}
        />
        <Select
          allowClear
          placeholder="结果"
          style={{ width: 120 }}
          value={result}
          onChange={setResult}
          options={[
            { value: 'success', label: '成功' },
            { value: 'failure', label: '失败' },
          ]}
        />
        <Select
          showSearch
          allowClear
          placeholder="操作者"
          style={{ width: 160 }}
          value={actor || undefined}
          onChange={setActor}
          options={[{ value: actor, label: actor }]}
        />
        <RangePicker value={range} onChange={(v) => setRange(v as [Dayjs | null, Dayjs | null] | null)} />
        <Button icon={<ReloadOutlined />} onClick={() => void search(1, pageSize)}>查询</Button>
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
          onChange: (p, ps) => { setPage(p); setPageSize(ps); void search(p, ps) },
        }}
      />
      <Modal
        title={activeLog.title || '操作会话日志内容'}
        open={logModalOpen}
        onCancel={() => setLogModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setLogModalOpen(false)}>关闭</Button>,
        ]}
        width={750}
        destroyOnHidden
      >
        <div style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary">服务器记录路径：</Typography.Text>
          <Typography.Text code copyable>{activeLog.path || '-'}</Typography.Text>
        </div>
        {activeLog.error && !activeLog.content && (
          <Typography.Text type="danger" style={{ display: 'block', marginBottom: 8 }}>
            {activeLog.error}
          </Typography.Text>
        )}
        <pre className="log-viewer">
          {activeLog.content || '暂无日志内容'}
        </pre>
      </Modal>
    </div>
  )
}
