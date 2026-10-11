import { Eye, Pencil, Plus, Power, PowerOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ConfirmModal } from '../components/forms/ConfirmModal.jsx'
import { NodeFormModal } from '../components/forms/NodeFormModal.jsx'
import { Button, IconButton } from '../components/ui/Button.jsx'
import { Card } from '../components/ui/Card.jsx'
import { Select, SearchInput } from '../components/ui/Fields.jsx'
import { PageHeader } from '../components/ui/Misc.jsx'
import { Pagination } from '../components/ui/Pagination.jsx'
import { DataState } from '../components/ui/States.jsx'
import { StatusBadge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useAuth } from '../hooks/useAuth.js'
import { useDebounce } from '../hooks/useDebounce.js'
import { useUrlState } from '../hooks/useUrlState.js'
import { listNodes, setNodeStatus } from '../services/nodes.js'
import { formatDateTime, formatNumber, relativeTime } from '../utils/format.js'
import { NODE_STATUSES, titleCase } from '../utils/status.js'

const DEFAULTS = { search: '', status: '', page: '1' }
const PAGE_SIZE = 25

export default function NodesPage() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const [filters, update] = useUrlState(DEFAULTS)
  const [text, setText] = useState(filters.search)
  const debouncedText = useDebounce(text, 300)
  const [editing, setEditing] = useState(null) // null | 'new' | node
  const [toggling, setToggling] = useState(null)

  useEffect(() => {
    if (debouncedText !== filters.search) update({ search: debouncedText })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedText])

  const page = Number(filters.page) || 1
  const result = useAsync(
    (signal) => listNodes({ search: filters.search, status: filters.status, page, pageSize: PAGE_SIZE }, signal),
    [filters.search, filters.status, page],
  )

  const hasFilters = Boolean(filters.search || filters.status)

  return (
    <>
      <PageHeader
        title="Nodes"
        subtitle="Authorized network observation points"
        actions={
          isAdmin && (
            <Button variant="primary" icon={Plus} onClick={() => setEditing('new')}>
              Add node
            </Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <SearchInput
            value={text}
            onChange={setText}
            placeholder="Search name, code, location or IP"
            label="Search nodes"
            className="w-full sm:w-72"
          />
          <Select
            aria-label="Filter by status"
            value={filters.status}
            onChange={(event) => update({ status: event.target.value })}
            className="w-40"
          >
            <option value="">All statuses</option>
            {NODE_STATUSES.map((status) => (
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
                update({ search: '', status: '' })
              }}
            >
              Clear
            </Button>
          )}
        </div>

        <DataState
          result={result}
          isEmpty={(data) => data.items.length === 0}
          empty={{
            title: hasFilters ? 'No nodes match your filters' : 'No nodes registered yet',
            hint: hasFilters ? 'Try changing or clearing the filters.' : isAdmin ? 'Add a node to start monitoring.' : undefined,
          }}
          errorTitle="Unable to load nodes"
        >
          {(data) => (
            <>
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>Node</Th>
                      <Th>Location</Th>
                      <Th>Status</Th>
                      <Th align="right">Devices</Th>
                      <Th>Last seen</Th>
                      <Th align="right">Actions</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((node) => (
                      <Tr key={node.node_id} onClick={() => navigate(`/nodes/${node.node_id}`)}>
                        <Td>
                          <p className="font-medium text-ink">{node.node_name}</p>
                          <p className="font-mono text-xs text-faint">
                            {node.node_code} · {node.ip_address}
                          </p>
                        </Td>
                        <Td className="text-muted">{node.location}</Td>
                        <Td>
                          <StatusBadge status={node.status} />
                        </Td>
                        <Td align="right">{formatNumber(node.device_count)}</Td>
                        <Td className="whitespace-nowrap" >
                          <span title={formatDateTime(node.last_seen)}>{relativeTime(node.last_seen)}</span>
                        </Td>
                        <Td align="right">
                          <div className="flex justify-end gap-0.5" onClick={(event) => event.stopPropagation()}>
                            <Link to={`/nodes/${node.node_id}`} aria-label={`View ${node.node_name}`} title="View details">
                              <span className="inline-flex size-8 items-center justify-center rounded-md text-muted hover:bg-panel-2 hover:text-ink">
                                <Eye size={16} aria-hidden="true" />
                              </span>
                            </Link>
                            {isAdmin && (
                              <>
                                <IconButton icon={Pencil} label={`Edit ${node.node_name}`} onClick={() => setEditing(node)} />
                                <IconButton
                                  icon={node.status === 'INACTIVE' ? Power : PowerOff}
                                  label={`${node.status === 'INACTIVE' ? 'Enable' : 'Disable'} ${node.node_name}`}
                                  onClick={() => setToggling(node)}
                                />
                              </>
                            )}
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
              <Pagination data={data} onPageChange={(next) => update({ page: next })} />
            </>
          )}
        </DataState>
      </Card>

      {editing && (
        <NodeFormModal
          node={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => result.reload()}
        />
      )}
      {toggling && (
        <ConfirmModal
          title={toggling.status === 'INACTIVE' ? `Enable ${toggling.node_name}?` : `Disable ${toggling.node_name}?`}
          message={
            toggling.status === 'INACTIVE'
              ? 'The node becomes Active again and its collectors can submit events.'
              : 'The node is marked Inactive and its collectors will be rejected. Its devices and history are preserved.'
          }
          confirmLabel={toggling.status === 'INACTIVE' ? 'Enable node' : 'Disable node'}
          danger={toggling.status !== 'INACTIVE'}
          onConfirm={async () => {
            await setNodeStatus(toggling.node_id, toggling.status === 'INACTIVE' ? 'ACTIVE' : 'INACTIVE')
            result.reload()
          }}
          onClose={() => setToggling(null)}
        />
      )}
    </>
  )
}
