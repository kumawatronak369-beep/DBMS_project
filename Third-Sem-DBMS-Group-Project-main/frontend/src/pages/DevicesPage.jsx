import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button.jsx'
import { Card } from '../components/ui/Card.jsx'
import { SearchInput, Select } from '../components/ui/Fields.jsx'
import { PageHeader } from '../components/ui/Misc.jsx'
import { Pagination } from '../components/ui/Pagination.jsx'
import { DataState } from '../components/ui/States.jsx'
import { StatusBadge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useDebounce } from '../hooks/useDebounce.js'
import { useUrlState } from '../hooks/useUrlState.js'
import { listDevices } from '../services/devices.js'
import { listNodes } from '../services/nodes.js'
import { formatDateTime, relativeTime } from '../utils/format.js'
import { DEVICE_STATUSES, titleCase } from '../utils/status.js'

const DEFAULTS = { search: '', nodeId: '', status: '', page: '1' }
const PAGE_SIZE = 25

export default function DevicesPage() {
  const navigate = useNavigate()
  const [filters, update] = useUrlState(DEFAULTS)
  const [text, setText] = useState(filters.search)
  const debouncedText = useDebounce(text, 300)

  useEffect(() => {
    if (debouncedText !== filters.search) update({ search: debouncedText })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedText])

  const page = Number(filters.page) || 1
  const nodes = useAsync((signal) => listNodes({ pageSize: 100 }, signal), [])
  const result = useAsync(
    (signal) =>
      listDevices(
        { search: filters.search, nodeId: filters.nodeId, status: filters.status, page, pageSize: PAGE_SIZE },
        signal,
      ),
    [filters.search, filters.nodeId, filters.status, page],
  )
  const hasFilters = Boolean(filters.search || filters.nodeId || filters.status)

  return (
    <>
      <PageHeader title="Devices" subtitle="Devices observed through authorized nodes" />

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <SearchInput
            value={text}
            onChange={setText}
            placeholder="Search identifier, name, IP or hostname"
            label="Search devices"
            className="w-full sm:w-72"
          />
          <Select
            aria-label="Filter by node"
            value={filters.nodeId}
            onChange={(event) => update({ nodeId: event.target.value })}
            className="w-48"
          >
            <option value="">All nodes</option>
            {nodes.data?.items.map((node) => (
              <option key={node.node_id} value={node.node_id}>
                {node.node_name}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filter by status"
            value={filters.status}
            onChange={(event) => update({ status: event.target.value })}
            className="w-40"
          >
            <option value="">All statuses</option>
            {DEVICE_STATUSES.map((status) => (
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
                update({ search: '', nodeId: '', status: '' })
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
            title: hasFilters ? 'No devices match your filters' : 'No devices found',
            hint: hasFilters ? 'Try changing or clearing the filters.' : 'Devices appear when a node reports events.',
          }}
          errorTitle="Unable to load devices"
        >
          {(data) => (
            <>
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>Device</Th>
                      <Th>IP address</Th>
                      <Th>Hostname</Th>
                      <Th>Node</Th>
                      <Th>First seen</Th>
                      <Th>Last seen</Th>
                      <Th>Status</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((device) => (
                      <Tr key={device.device_id} onClick={() => navigate(`/devices/${device.device_id}`)}>
                        <Td>
                          <p className="font-medium text-ink">{device.device_identifier}</p>
                          {device.device_name && <p className="text-xs text-faint">{device.device_name}</p>}
                        </Td>
                        <Td mono>{device.ip_address}</Td>
                        <Td mono className="text-muted">
                          {device.hostname ?? '—'}
                        </Td>
                        <Td onClick={(event) => event.stopPropagation()}>
                          <Link to={`/nodes/${device.node_id}`} className="text-muted hover:text-accent">
                            {device.node_name}
                          </Link>
                        </Td>
                        <Td className="whitespace-nowrap text-muted">{formatDateTime(device.first_seen)}</Td>
                        <Td className="whitespace-nowrap">
                          <span title={formatDateTime(device.last_seen)}>{relativeTime(device.last_seen)}</span>
                        </Td>
                        <Td>
                          <StatusBadge status={device.status} />
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
    </>
  )
}
