import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Typography, message } from 'antd'
import { LockOutlined, SafetyOutlined, UserOutlined } from '@ant-design/icons'
import { useAuth } from '../contexts/AuthContext'
import { extractError } from '../api/client'

const { Title, Text } = Typography

export default function LoginPage() {
  const { login, verifyMfa, user } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mfaToken, setMfaToken] = useState<string | null>(null)

  if (user) {
    navigate('/dashboard', { replace: true })
  }

  const onPasswordSubmit = async (values: { username: string; password: string }) => {
    setLoading(true)
    setError(null)
    try {
      const result = await login(values.username, values.password)
      if (result.mfa_required && result.mfa_token) {
        setMfaToken(result.mfa_token)
        message.info('请输入动态验证码完成二次验证')
      } else {
        navigate('/dashboard', { replace: true })
      }
    } catch (err) {
      setError(extractError(err, '登录失败，请检查用户名或密码'))
    } finally {
      setLoading(false)
    }
  }

  const onMfaSubmit = async (values: { code: string }) => {
    if (!mfaToken) return
    setLoading(true)
    setError(null)
    try {
      await verifyMfa(mfaToken, values.code)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(extractError(err, '验证码校验失败'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <Card className="login-card">
        <Title level={3} className="login-title">
          lycloud4A 统一身份管控平台
        </Title>
        <Text type="secondary" className="login-subtitle">
          认证 · 授权 · 账号 · 审计
        </Text>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
        {mfaToken ? (
          <Form layout="vertical" onFinish={onMfaSubmit} requiredMark={false}>
            <Form.Item
              name="code"
              label="动态验证码（MFA）"
              rules={[{ required: true, message: '请输入动态验证码' }]}
            >
              <Input
                size="large"
                prefix={<SafetyOutlined />}
                placeholder="6 位验证码"
                maxLength={6}
                autoFocus
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={loading}>
              验证并登录
            </Button>
            <Button type="link" block onClick={() => setMfaToken(null)} style={{ marginTop: 8 }}>
              返回重新输入账号
            </Button>
          </Form>
        ) : (
          <Form layout="vertical" onFinish={onPasswordSubmit} requiredMark={false} initialValues={{ username: 'admin' }}>
            <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
              <Input size="large" prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password
                size="large"
                prefix={<LockOutlined />}
                placeholder="密码"
                autoComplete="current-password"
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={loading}>
              登 录
            </Button>
          </Form>
        )}
        <Text type="secondary" style={{ display: 'block', marginTop: 16, fontSize: 12 }}>
          默认管理员：admin / Admin@12345（首次登录后请立即修改密码）
        </Text>
      </Card>
    </div>
  )
}
