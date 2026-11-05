import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, Chip, ErrorBox, Field, Modal, PageTitle } from '../components/ui'

interface UnitNode {
  id: string
  name: string
  code: string | null
  manager_name: string | null
  deputy_manager_name: string | null
  children: UnitNode[]
}

export default function OrgUnits() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [parentId, setParentId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: tree, isLoading } = useQuery<UnitNode[]>({
    queryKey: ['unit-tree'],
    queryFn: () => api('/organization-units/tree'),
  })

  const create = useMutation({
    mutationFn: (body: any) => api('/organization-units', { body }),
    onSuccess: () => { setOpen(false); setError(null); qc.invalidateQueries({ queryKey: ['unit-tree'] }) },
    onError: (e: any) => setError(e.message),
  })

  const renderNode = (node: UnitNode, depth = 0) => (
    <div key={node.id}>
      <div className="card" style={{ marginInlineStart: depth * 22, padding: '10px 14px', marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div>
            <strong>{node.name}</strong> {node.code && <Chip label={node.code} tone="gray" />}
            <div className="muted">
              مدیر: {node.manager_name ?? '—'} {node.deputy_manager_name && <>· جانشین: {node.deputy_manager_name}</>}
            </div>
          </div>
          <button className="btn btn-sm" onClick={() => { setParentId(node.id); setOpen(true) }}>+ زیرواحد</button>
        </div>
      </div>
      {node.children?.map((c) => renderNode(c, depth + 1))}
    </div>
  )

  return (
    <div>
      <PageTitle
        title="ساختار سازمانی"
        subtitle="واحدها، زیرواحدها و مدیران — انتقال بین واحدها تاریخچه حفظ می‌کند (سند ۵.۱)"
        actions={<button className="btn btn-primary" onClick={() => { setParentId(null); setOpen(true) }}>+ واحد ریشه</button>}
      />
      <ErrorBox message={error} />
      {isLoading ? <div className="page-loading">…</div> : (tree ?? []).map((n) => renderNode(n))}

      <Modal open={open} title={parentId ? 'ایجاد زیرواحد' : 'ایجاد واحد ریشه'} onClose={() => setOpen(false)}>
        <ErrorBox message={error} />
        <form onSubmit={(e) => {
          e.preventDefault()
          const fd = new FormData(e.currentTarget as HTMLFormElement)
          create.mutate({
            name: fd.get('name'),
            code: fd.get('code') || null,
            parent_id: parentId,
            manager_id: fd.get('manager_id') || null,
            deputy_manager_id: fd.get('deputy_manager_id') || null,
            description: fd.get('description') || null,
          })
        }}>
          <Field label="نام واحد *"><input name="name" required minLength={2} /></Field>
          <Field label="کد واحد"><input name="code" dir="ltr" /></Field>
          <Field label="شناسه مدیر (UUID)"><input name="manager_id" dir="ltr" /></Field>
          <Field label="شناسه جانشین مدیر (UUID)"><input name="deputy_manager_id" dir="ltr" /></Field>
          <Field label="توضیح"><textarea name="description" /></Field>
          <button className="btn btn-primary" disabled={create.isPending}>ایجاد</button>
        </form>
      </Modal>
    </div>
  )
}
