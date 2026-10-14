import { useEffect, useState } from 'react'
import { Card, Col, List, Row, Statistic, Table, Tag, Typography, message } from 'antd'
import {
  AppstoreOutlined,
  AuditOutlined,
  KeyOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { dashboardApi } from '../api/endpoints'
import { extractError } from '../api/client'
import { useThemeMode } from '../contexts/ThemeContext'
import { chartPalette, semanticColors } from '../theme'
import type { DashboardStats } from '../types'

const { Title } = Typography

const resultColor: Record<string, string> = { success: 'green', failure: 'red' }

export default function DashboardPage() {
  const { mode } = useThemeMode()
  const palette = chartPalette(mode)
  const semantic = semanticColors(mode)
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void (async () => {
      try {
        setStats(await dashboardApi.stats())
      } catch (err) {
        message.error(extractError(err, '加载仪表盘失败'))
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const tooltipStyle = {
    background: palette.tooltipBg,
    border: `1px solid ${palette.tooltipBorder}`,
    borderRadius: 8,
    color: palette.tooltipText,
  }

  return (
    <div>
      <Title level={4} className="page-title">平台概览</Title>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="用户总数" value={stats?.user_total ?? 0} prefix={<UserOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="启用用户" value={stats?.user_active ?? 0} valueStyle={{ color: semantic.success }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="停用用户" value={stats?.user_disabled ?? 0} valueStyle={{ color: semantic.danger }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="接入应用" value={stats?.app_total ?? 0} prefix={<AppstoreOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="角色数" value={stats?.role_total ?? 0} prefix={<SafetyCertificateOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="托管密钥" value={stats?.secret_total ?? 0} prefix={<KeyOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic
              title="待轮换密钥"
              value={stats?.secret_rotation_due ?? 0}
              valueStyle={{ color: (stats?.secret_rotation_due ?? 0) > 0 ? semantic.warning : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="今日登录" value={stats?.login_today ?? 0} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic
              title="今日失败"
              value={stats?.login_failed_today ?? 0}
              valueStyle={{ color: (stats?.login_failed_today ?? 0) > 0 ? semantic.danger : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="MFA 启用率" value={stats?.mfa_enabled_rate ?? 0} suffix="%" />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="审计总量" value={stats?.audit_total ?? 0} prefix={<AuditOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card className="stat-card" loading={loading}>
            <Statistic title="策略数" value={stats?.policy_total ?? 0} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="近 7 天登录趋势" loading={loading}>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={stats?.login_trend ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
                <XAxis dataKey="date" stroke={palette.axis} tick={{ fill: palette.axis, fontSize: 12 }} />
                <YAxis allowDecimals={false} stroke={palette.axis} tick={{ fill: palette.axis, fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="登录次数"
                  stroke={palette.line}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="审计类别分布" loading={loading}>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={stats?.category_distribution ?? []}
                  dataKey="count"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label
                >
                  {(stats?.category_distribution ?? []).map((_entry, index) => (
                    <Cell key={index} fill={palette.series[index % palette.series.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="各维度登录次数" loading={loading}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={stats?.login_trend ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
                <XAxis dataKey="date" stroke={palette.axis} tick={{ fill: palette.axis, fontSize: 12 }} />
                <YAxis allowDecimals={false} stroke={palette.axis} tick={{ fill: palette.axis, fontSize: 12 }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: palette.grid }} />
                <Bar dataKey="count" name="登录次数" fill={palette.bar} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="最近审计事件" loading={loading}>
            <List
              size="small"
              dataSource={stats?.recent_audits ?? []}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <span>
                        {item.actor_username || 'system'} → {item.action}{' '}
                        <Tag color={resultColor[item.result] || 'default'}>{item.result}</Tag>
                      </span>
                    }
                    description={item.target_name || item.message || '-'}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: 16 }} title="审计趋势明细" loading={loading}>
        <Table
          size="small"
          rowKey="date"
          pagination={false}
          dataSource={stats?.login_trend ?? []}
          columns={[
            { title: '日期', dataIndex: 'date' },
            { title: '登录次数', dataIndex: 'count' },
          ]}
        />
      </Card>
    </div>
  )
}
