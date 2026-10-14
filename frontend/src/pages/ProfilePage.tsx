import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { authApi } from '../api/endpoints'
import { extractError } from '../api/client'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { QRCodeSVG } from 'qrcode.react'

const { Title } = Typography

export default function ProfilePage() {
  const { user, reload } = useAuth()
  const [pwdForm] = Form.useForm()
  const [mfaOpen, setMfaOpen] = useState(false)
  const [mfaSecret, setMfaSecret] = useState<string | null>(null)
  const [mfaUrl, setMfaUrl] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  const changePassword = async (values: { old_password: string; new_password: string }) => {
    try {
      await authApi.changePassword(values)
      message.success('密码已修改')
      pwdForm.resetFields()
    } catch (err) {
      message.error(extractError(err, '修改密码失败'))
    }
  }

  const startMfaSetup = async () => {
    try {
      const data = await authApi.mfaSetup()
      setMfaSecret(data.secret)
      setMfaUrl(data.otpauth_url)
      setMfaOpen(true)
    } catch (err) {
      message.error(extractError(err, '初始化 MFA 失败'))
    }
  }

  const confirmMfa = async (values: { code: string }) => {
    setConfirming(true)
    try {
      await authApi.mfaEnable({ code: values.code })
      message.success('MFA 已启用')
      setMfaOpen(false)
      await reload()
    } catch (err) {
      message.error(extractError(err, '验证码错误'))
    } finally {
      setConfirming(false)
    }
  }

  const disableMfa = async (values: { code: string }) => {
    try {
      await authApi.mfaDisable({ code: values.code })
      message.success('MFA 已停用')
      await reload()
    } catch (err) {
      message.error(extractError(err, '停用失败'))
    }
  }

  return (
    <div>
      <Title level={4} className="page-title">个人中心</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="账户信息">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="用户名">{user?.username}</Descriptions.Item>
              <Descriptions.Item label="显示名">{user?.display_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="邮箱">{user?.email || '-'}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={user?.status === 'active' ? 'green' : 'red'}>{user?.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="角色">
                {user?.roles?.length
                  ? user.roles.map((r) => <Tag key={r.id}>{r.name}</Tag>)
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="MFA">
                {user?.mfa_enabled ? <Tag color="green">已启用</Tag> : <Tag>未启用</Tag>}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="修改密码">
            <Form form={pwdForm} layout="vertical" onFinish={changePassword}>
              <Form.Item
                name="old_password"
                label="当前密码"
                rules={[{ required: true, message: '请输入当前密码' }]}
              >
                <Input.Password />
              </Form.Item>
              <Form.Item
                name="new_password"
                label="新密码"
                rules={[
                  { required: true, message: '请输入新密码' },
                  { min: 8, message: '密码至少 8 位' },
                ]}
              >
                <Input.Password />
              </Form.Item>
              <Button type="primary" htmlType="submit">
                更新密码
              </Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24}>
          <Card title="双因子认证（MFA）">
            {user?.mfa_enabled ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Alert type="success" showIcon message="MFA 已启用，登录时需要动态验证码。" />
                <Form layout="inline" onFinish={disableMfa}>
                  <Form.Item name="code" rules={[{ required: true, message: '请输入验证码' }]}>
                    <Input placeholder="输入 6 位验证码以停用" maxLength={6} />
                  </Form.Item>
                  <Button danger htmlType="submit">
                    停用 MFA
                  </Button>
                </Form>
              </Space>
            ) : (
              <Space direction="vertical">
                <Alert type="info" showIcon message="启用 MFA 可显著提升账户安全性。" />
                <Button type="primary" onClick={startMfaSetup}>
                  启用 MFA
                </Button>
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="启用 MFA"
        open={mfaOpen}
        footer={null}
        onCancel={() => setMfaOpen(false)}
        destroyOnHidden
      >
        <Space direction="vertical" style={{ width: '100%' }} align="center">
          {mfaUrl && <QRCodeSVG value={mfaUrl} size={180} />}
          <Typography.Text copyable>{mfaSecret}</Typography.Text>
          <Typography.Text type="secondary">
            使用 Google Authenticator / Microsoft Authenticator 扫码，然后输入验证码。
          </Typography.Text>
          <Form layout="vertical" onFinish={confirmMfa} style={{ width: '100%' }}>
            <Form.Item name="code" rules={[{ required: true, message: '请输入验证码' }]}>
              <Input placeholder="6 位验证码" maxLength={6} autoFocus />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={confirming}>
              确认启用
            </Button>
          </Form>
        </Space>
      </Modal>
    </div>
  )
}
