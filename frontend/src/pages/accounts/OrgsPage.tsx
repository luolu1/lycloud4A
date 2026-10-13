import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Table,
  TreeSelect,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { orgApi } from '../../api/endpoints'
import { extractError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import type { OrgOut, OrgTreeNode } from '../../types'

const { Title } = Typography

interface TreeSelectNode {
  value: number
  title: string
  children?: TreeSelectNode[]
}

function toTreeSelectData(nodes: OrgTreeNode[]): TreeSelectNode[] {
  return nodes.map((n) => ({
    value: n.id,
    title: `${n.name} (${n.code})`,
    children: n.children ? toTreeSelectData(n.children) : undefined,
  }))
}

export default function OrgsPage() {
  const { message } = App.useApp()
  const { can } = useAuth()
  const [data, setData] = useState<OrgOut[]>([])
  const [tree, setTree] = useState<OrgTreeNode[]>([])
  const [loading, setLoading] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<OrgOut | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [list, treeData] = await Promise.all([orgApi.list(), orgApi.tree()])
      setData(list)
      setTree(treeData)
    } catch (err) {
      message.error(extractError(err, '加载组织架构失败'))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = (parentId?: number) => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ parent_id: parentId, sort_order: 0 })
    setEditOpen(true)
  }

  const openEdit = (record: OrgOut) => {
    setEditing(record)
    form.setFieldsValue(record)
    setEditOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await orgApi.update(editing.id, values)
        message.success('组织已更新')
      } else {
        await orgApi.create(values)
        message.success('组织已创建')
      }
      setEditOpen(false)
      await load()
    } catch (err) {
      message.error(extractError(err, '保存失败'))
    }
  }

  const remove = async (record: OrgOut) => {
    try {
      await orgApi.remove(record.id)
      message.success('组织已删除')
      await load()
    } catch (err) {
      message.error(extractError(err, '删除失败'))
    }
  }

  const columns: ColumnsType<OrgOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '名称', dataIndex: 'name' },
    { title: '编码', dataIndex: 'code' },
    { title: '上级组织', dataIndex: 'parent_id', width: 100, render: (v) => {
        if (!v) return '-'
        const parent = data.find((o) => o.id === v)
        return parent ? parent.name : v
      } },
    { title: '描述', dataIndex: 'description', render: (v) => v || '-' },
    { title: '排序', dataIndex: 'sort_order', width: 80 },
    {
      title: '操作',
      width: 220,
      render: (_v, record) => (
        <Space size="small" wrap>
          {can('org:write') && (
            <Button type="link" size="small" onClick={() => openCreate(record.id)}>新建子级</Button>
          )}
          {can('org:write') && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>编辑</Button>
          )}
          {can('org:delete') && (
            <Popconfirm title="确认删除该组织？" onConfirm={() => void remove(record)}>
              <Button type="link" size="small" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4}>组织架构</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
        {can('org:write') && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate()}>新建顶级组织</Button>
        )}
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data}
        pagination={false}
        expandable={{
          defaultExpandAllRows: false,
          rowExpandable: (r) => data.some((o) => o.parent_id === r.id),
        }}
      />

      <Modal
        title={editing ? '编辑组织' : '新建组织'}
        open={editOpen}
        onOk={submit}
        onCancel={() => setEditOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="parent_id" label="上级组织">
            <TreeSelect
              allowClear
              treeDefaultExpandAll
              treeData={toTreeSelectData(tree)}
              placeholder="不选则为顶级组织"
              onChange={() => undefined}
            />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入编码' }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序" initialValue={0}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}