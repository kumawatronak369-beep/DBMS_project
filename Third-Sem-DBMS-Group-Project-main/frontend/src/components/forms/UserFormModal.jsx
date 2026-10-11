import { useState } from 'react'
import { createUser, updateUser } from '../../services/users.js'
import { titleCase, USER_ROLES } from '../../utils/status.js'
import { Button } from '../ui/Button.jsx'
import { Field, Select, TextInput } from '../ui/Fields.jsx'
import { Modal } from '../ui/Modal.jsx'

const MIN_PASSWORD = 8

export function UserFormModal({ user, onClose, onSaved }) {
  const editing = Boolean(user)
  const [values, setValues] = useState({
    name: user?.name ?? '',
    email: user?.email ?? '',
    role: user?.role ?? 'ANALYST',
    password: '',
  })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState(null)
  const [pending, setPending] = useState(false)

  const set = (field) => (event) => setValues((current) => ({ ...current, [field]: event.target.value }))

  function validate() {
    const found = {}
    if (!values.name.trim()) found.name = 'Name is required'
    if (!/^[^@\s]+@[^@\s]+$/.test(values.email.trim())) found.email = 'Enter a valid email address'
    if (!editing && values.password.length < MIN_PASSWORD) found.password = `At least ${MIN_PASSWORD} characters`
    if (editing && values.password && values.password.length < MIN_PASSWORD) {
      found.password = `At least ${MIN_PASSWORD} characters`
    }
    return found
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setPending(true)
    setServerError(null)
    const payload = { name: values.name.trim(), email: values.email.trim(), role: values.role }
    if (values.password) payload.password = values.password
    try {
      const saved = editing ? await updateUser(user.user_id, payload) : await createUser({ ...payload })
      onSaved(saved)
      onClose()
    } catch (error) {
      setServerError(error.message)
      setPending(false)
    }
  }

  return (
    <Modal
      title={editing ? `Edit ${user.name}` : 'Add user'}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="user-form" loading={pending}>
            {editing ? 'Save changes' : 'Add user'}
          </Button>
        </>
      }
    >
      <form id="user-form" onSubmit={handleSubmit} noValidate className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {serverError && (
          <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger sm:col-span-2" role="alert">
            {serverError}
          </p>
        )}
        <Field label="Name" error={errors.name}>
          {(id) => <TextInput id={id} value={values.name} onChange={set('name')} maxLength={100} autoFocus />}
        </Field>
        <Field label="Email" error={errors.email}>
          {(id) => <TextInput id={id} type="email" value={values.email} onChange={set('email')} maxLength={255} autoComplete="off" />}
        </Field>
        <Field label="Role">
          {(id) => (
            <Select id={id} value={values.role} onChange={set('role')}>
              {USER_ROLES.map((role) => (
                <option key={role} value={role}>
                  {titleCase(role)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          label={editing ? 'New password' : 'Password'}
          error={errors.password}
          hint={editing ? 'Leave blank to keep the current password' : `At least ${MIN_PASSWORD} characters`}
        >
          {(id) => (
            <TextInput id={id} type="password" value={values.password} onChange={set('password')} autoComplete="new-password" />
          )}
        </Field>
      </form>
    </Modal>
  )
}
