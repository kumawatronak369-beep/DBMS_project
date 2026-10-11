import { Pencil, Plus, Power, PowerOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ConfirmModal } from '../components/forms/ConfirmModal.jsx'
import { UserFormModal } from '../components/forms/UserFormModal.jsx'
import { Button, IconButton } from '../components/ui/Button.jsx'
import { Card } from '../components/ui/Card.jsx'
import { SearchInput, Select } from '../components/ui/Fields.jsx'
import { PageHeader } from '../components/ui/Misc.jsx'
import { Pagination } from '../components/ui/Pagination.jsx'
import { DataState } from '../components/ui/States.jsx'
import { StatusBadge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useAuth } from '../hooks/useAuth.js'
import { useDebounce } from '../hooks/useDebounce.js'
import { useUrlState } from '../hooks/useUrlState.js'
import { listUsers, setUserStatus } from '../services/users.js'
import { formatDateTime, relativeTime } from '../utils/format.js'
import { titleCase, USER_ROLES, USER_STATUSES } from '../utils/status.js'

const DEFAULTS = { search: '', role: '', status: '', page: '1' }
const PAGE_SIZE = 25

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const [filters, update] = useUrlState(DEFAULTS)
  const [text, setText] = useState(filters.search)
  const debouncedText = useDebounce(text, 300)
  const [editing, setEditing] = useState(null) // null | 'new' | user
  const [toggling, setToggling] = useState(null)

  useEffect(() => {
    if (debouncedText !== filters.search) update({ search: debouncedText })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedText])

  const page = Number(filters.page) || 1
  const result = useAsync(
    (signal) =>
      listUsers({ search: filters.search, role: filters.role, status: filters.status, page, pageSize: PAGE_SIZE }, signal),
    [filters.search, filters.role, filters.status, page],
  )
  const hasFilters = Boolean(filters.search || filters.role || filters.status)

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Accounts that can sign in to this system"
        actions={
          <Button variant="primary" icon={Plus} onClick={() => setEditing('new')}>
            Add user
          </Button>
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <SearchInput value={text} onChange={setText} placeholder="Search name or email" label="Search users" className="w-full sm:w-72" />
          <Select aria-label="Filter by role" value={filters.role} onChange={(event) => update({ role: event.target.value })} className="w-36">
            <option value="">All roles</option>
            {USER_ROLES.map((role) => (
              <option key={role} value={role}>
                {titleCase(role)}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by status" value={filters.status} onChange={(event) => update({ status: event.target.value })} className="w-36">
            <option value="">All statuses</option>
            {USER_STATUSES.map((status) => (
              <option key={status} value={status}>
                {titleCase(status)}
              </option>
            ))}
          </Select>
          {hasFilters && (
            <Button
              variant="ghost"
              onClick={() => {
                setText('')
                update({ search: '', role: '', status: '' })
              }}
            >
              Clear
            </Button>
          )}
        </div>

        <DataState
          result={result}
          isEmpty={(data) => data.items.length === 0}
          empty={{ title: hasFilters ? 'No users match your filters' : 'No users found', hint: hasFilters ? 'Try changing or clearing the filters.' : undefined }}
          errorTitle="Unable to load users"
        >
          {(data) => (
            <>
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>User</Th>
                      <Th>Email</Th>
                      <Th>Role</Th>
                      <Th>Status</Th>
                      <Th>Created</Th>
                      <Th>Last login</Th>
                      <Th align="right">Actions</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((user) => {
                      const isSelf = user.user_id === currentUser?.user_id
                      const disabled = user.status === 'DISABLED'
                      return (
                        <Tr key={user.user_id}>
                          <Td className="font-medium">
                            {user.name}
                            {isSelf && <span className="ml-2 text-[11px] font-normal text-faint">(you)</span>}
                          </Td>
                          <Td mono className="text-muted">
                            {user.email}
                          </Td>
                          <Td>
                            <StatusBadge status={user.role} />
                          </Td>
                          <Td>
                            <StatusBadge status={user.status} />
                          </Td>
                          <Td className="whitespace-nowrap text-muted">{formatDateTime(user.created_at)}</Td>
                          <Td className="whitespace-nowrap">
                            <span title={formatDateTime(user.last_login)}>{user.last_login ? relativeTime(user.last_login) : 'Never'}</span>
                          </Td>
                          <Td align="right">
                            <div className="flex justify-end gap-0.5">
                              <IconButton icon={Pencil} label={`Edit ${user.name}`} onClick={() => setEditing(user)} />
                              <IconButton
                                icon={disabled ? Power : PowerOff}
                                label={isSelf ? 'You cannot disable your own account' : `${disabled ? 'Enable' : 'Disable'} ${user.name}`}
                                disabled={isSelf}
                                onClick={() => setToggling(user)}
                              />
                            </div>
                          </Td>
                        </Tr>
                      )
                    })}
                  </tbody>
                </Table>
              </TableWrap>
              <Pagination data={data} onPageChange={(next) => update({ page: next })} />
            </>
          )}
        </DataState>
      </Card>

      {editing && (
        <UserFormModal user={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => result.reload()} />
      )}
      {toggling && (
        <ConfirmModal
          title={toggling.status === 'DISABLED' ? `Enable ${toggling.name}?` : `Disable ${toggling.name}?`}
          message={
            toggling.status === 'DISABLED'
              ? 'This user will be able to sign in again.'
              : 'This user will be signed out and unable to sign in. Their account is kept, not deleted.'
          }
          confirmLabel={toggling.status === 'DISABLED' ? 'Enable user' : 'Disable user'}
          danger={toggling.status !== 'DISABLED'}
          onConfirm={async () => {
            await setUserStatus(toggling.user_id, toggling.status === 'DISABLED' ? 'ACTIVE' : 'DISABLED')
            result.reload()
          }}
          onClose={() => setToggling(null)}
        />
      )}
    </>
  )
}
