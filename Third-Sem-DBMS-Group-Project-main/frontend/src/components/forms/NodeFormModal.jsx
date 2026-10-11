import { useState } from 'react'
import { createNode, updateNode } from '../../services/nodes.js'
import { Button } from '../ui/Button.jsx'
import { Field, TextInput } from '../ui/Fields.jsx'
import { Modal } from '../ui/Modal.jsx'

const EMPTY = { node_code: '', node_name: '', ip_address: '', location: '', description: '' }

function validate(values) {
  const errors = {}
  if (!values.node_code.trim()) errors.node_code = 'Node code is required'
  if (!values.node_name.trim()) errors.node_name = 'Name is required'
  if (!values.ip_address.trim()) errors.ip_address = 'IP address is required'
  if (!values.location.trim()) errors.location = 'Location is required'
  if (values.description.length > 500) errors.description = 'At most 500 characters'
  return errors
}

export function NodeFormModal({ node, onClose, onSaved }) {
  const editing = Boolean(node)
  const [values, setValues] = useState(
    node
      ? {
          node_code: node.node_code,
          node_name: node.node_name,
          ip_address: node.ip_address,
          location: node.location,
          description: node.description ?? '',
        }
      : EMPTY,
  )
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState(null)
  const [pending, setPending] = useState(false)

  const set = (field) => (event) => setValues((current) => ({ ...current, [field]: event.target.value }))

  async function handleSubmit(event) {
    event.preventDefault()
    const found = validate(values)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setPending(true)
    setServerError(null)
    const payload = { ...values, description: values.description.trim() || null }
    try {
      const saved = editing ? await updateNode(node.node_id, payload) : await createNode(payload)
      onSaved(saved)
      onClose()
    } catch (error) {
      setServerError(error.message)
      setPending(false)
    }
  }

  return (
    <Modal
      title={editing ? `Edit ${node.node_name}` : 'Add node'}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="node-form" loading={pending}>
            {editing ? 'Save changes' : 'Add node'}
          </Button>
        </>
      }
    >
      <form id="node-form" onSubmit={handleSubmit} noValidate className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {serverError && (
          <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger sm:col-span-2" role="alert">
            {serverError}
          </p>
        )}
        <Field label="Node code" error={errors.node_code} hint="Unique, e.g. LAB-A">
          {(id) => <TextInput id={id} value={values.node_code} onChange={set('node_code')} maxLength={50} autoFocus />}
        </Field>
        <Field label="Name" error={errors.node_name}>
          {(id) => <TextInput id={id} value={values.node_name} onChange={set('node_name')} maxLength={100} />}
        </Field>
        <Field label="IP address" error={errors.ip_address} hint="IPv4 or IPv6">
          {(id) => <TextInput id={id} value={values.ip_address} onChange={set('ip_address')} maxLength={45} className="font-mono" />}
        </Field>
        <Field label="Location" error={errors.location}>
          {(id) => <TextInput id={id} value={values.location} onChange={set('location')} maxLength={150} />}
        </Field>
        <Field label="Description" error={errors.description} className="sm:col-span-2">
          {(id) => <TextInput id={id} value={values.description} onChange={set('description')} placeholder="Optional" />}
        </Field>
      </form>
    </Modal>
  )
}
