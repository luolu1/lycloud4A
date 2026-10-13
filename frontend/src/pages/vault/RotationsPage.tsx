import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Card,
  List,
  Space,
  Statistic,
  Tag,
  Typography,
} from 'antd'
import { KeyOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { rotationApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { RotationRunResult, SecretOut } from '../../types'
import { formatDateTime } from '../../utils/format'

const { Title } = Typography

export default function RotationsPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [due, setDue] = useState<SecretOut[]>([])
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [lastRun, setLastRun] = useState<RotationRunResult | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setDue(await rotationApi.due())
    } catch (err) {
      message.error(extractError(err, '加载到期列表失败'))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  const runNow = async () => {
    setRunning(true)
    try {
      const result = await rotationApi.run()
      setLastRun(result)
      message.success(`轮换完成：成功 ${result.succeeded} / 失败 ${result.failed}`)
      await load()
    } catch (err) {
      message.error(extractError(err, '轮换执行失败'))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <Title level={4}>自动轮换</Title>
      <Card style={{ marginBottom: 16 }}>
        <Space size="large" wrap>
          <Statistic title="到期待轮换" value={due.length} prefix={<KeyOutlined />} />
          {can('secret:rotate') && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={running}
              onClick={() => void runNow()}
            >
              立即执行轮换扫描
            </Button>
          )}
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
            刷新
          </Button>
        </Space>
      </Card>

      {lastRun && (
        <Card title="最近一次执行结果" style={{ marginBottom: 16 }}>
          <Statistic
            title="处理 / 成功 / 失败"
            value={`${lastRun.processed} / ${lastRun.succeeded} / ${lastRun.failed}`}
          />
          <List
            size="small"
            dataSource={lastRun.results}
            renderItem={(item) => (
              <List.Item>
                <span>
                  {item.path}{' '}
                  <Tag color={item.success ? 'green' : 'red'}>{item.success ? '成功' : '失败'}</Tag>
                  {item.success && item.new_version != null && <Tag>新版本 v{item.new_version}</Tag>}
                  {!item.success && <Typography.Text type="secondary">{item.message}</Typography.Text>}
                </span>
              </List.Item>
            )}
          />
        </Card>
      )}

      <Card title="当前到期未轮换的密钥（由定时任务 / 手动触发处理）">
        <List
          loading={loading}
          dataSource={due}
          locale={{ emptyText: '没有到期未轮换的密钥' }}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={
                  <Space>
                    {item.name}
                    <Tag>{item.rotation_type}</Tag>
                    <Tag color="orange">v{item.current_version}</Tag>
                  </Space>
                }
                description={
                  <span>
                    路径 {item.path} · 下次轮换 {formatDateTime(item.next_rotation_at)}
                    {item.last_rotation_error && (
                      <Typography.Text type="danger" style={{ marginLeft: 8 }}>
                        {item.last_rotation_error}
                      </Typography.Text>
                    )}
                  </span>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}