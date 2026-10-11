import { Search, X } from 'lucide-react'
import { useState } from 'react'
import { EventDrawer } from '../components/EventDrawer.jsx'
import { HistoryTable } from '../components/HistoryTable.jsx'
import { Button } from '../components/ui/Button.jsx'
import { Card } from '../components/ui/Card.jsx'
import { Field, Select, TextInput } from '../components/ui/Fields.jsx'
import { PageHeader } from '../components/ui/Misc.jsx'
import { Pagination } from '../components/ui/Pagination.jsx'
import { DataState } from '../components/ui/States.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useUrlState } from '../hooks/useUrlState.js'
import { listDestinations } from '../services/destinations.js'
import { listHistory } from '../services/history.js'
import { listNodes } from '../services/nodes.js'
import { destinationLabel, formatNumber } from '../utils/format.js'

const DEFAULTS = { q: '', nodeId: '', destinationId: '', startDate: '', endDate: '', pageSize: '25', page: '1' }
const FILTER_KEYS = ['q', 'nodeId', 'destinationId', 'startDate', 'endDate']

export default function HistoryPage() {
  const [filters, update] = useUrlState(DEFAULTS)
  // the form is a draft; filters are applied when Search is pressed
  const [draft, setDraft] = useState(() => Object.fromEntries(FILTER_KEYS.map((key) => [key, filters[key]])))
  const [selectedEvent, setSelectedEvent] = useState(null)

  const page = Number(filters.page) || 1
  const pageSize = Number(filters.pageSize) || 25
  const dateError = draft.startDate && draft.endDate && draft.startDate > draft.endDate ? 'Start date is after the end date' : null

  const nodes = useAsync((signal) => listNodes({ pageSize: 100 }, signal), [])
  const destinations = useAsync((signal) => listDestinations({ pageSize: 100 }, signal), [])
  const result = useAsync(
    (signal) =>
      listHistory(
        {
          q: filters.q,
          nodeId: filters.nodeId,
          destinationId: filters.destinationId,
          startDate: filters.startDate,
          endDate: filters.endDate,
          page,
          pageSize,
        },
        signal,
      ),
    [filters.q, filters.nodeId, filters.destinationId, filters.startDate, filters.endDate, page, pageSize],
  )

  const hasFilters = FILTER_KEYS.some((key) => filters[key])
  const setField = (field) => (event) => setDraft((current) => ({ ...current, [field]: event.target.value }))

  function applyFilters(event) {
    event.preventDefault()
    if (dateError) return
    update({ ...draft, q: draft.q.trim() })
  }

  function clearFilters() {
    const cleared = Object.fromEntries(FILTER_KEYS.map((key) => [key, '']))
    setDraft(cleared)
    update(cleared)
  }

  return (
    <>
      <PageHeader
        title="Network history"
        subtitle={result.data ? `${formatNumber(result.data.total)} stored events${hasFilters ? ' match your filters' : ''}` : 'Search and investigate observed network activity'}
      />

      <Card>
        <form onSubmit={applyFilters} className="grid grid-cols-1 gap-3 border-b border-line p-3 md:grid-cols-2 xl:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto]" noValidate>
          <Field label="Search device, IP or domain">
            {(id) => <TextInput id={id} type="search" value={draft.q} onChange={setField('q')} placeholder="e.g. PC-LAB-A-001, 192.168.10.21, github" />}
          </Field>
          <Field label="Node">
            {(id) => (
              <Select id={id} value={draft.nodeId} onChange={setField('nodeId')}>
                <option value="">All nodes</option>
                {nodes.data?.items.map((node) => (
                  <option key={node.node_id} value={node.node_id}>
                    {node.node_name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Destination">
            {(id) => (
              <Select id={id} value={draft.destinationId} onChange={setField('destinationId')}>
                <option value="">All destinations</option>
                {[...(destinations.data?.items ?? [])]
                  .sort((a, b) => destinationLabel(a.domain, a.ip_address).localeCompare(destinationLabel(b.domain, b.ip_address)))
                  .map((destination) => (
                  <option key={destination.destination_id} value={destination.destination_id}>
                    {destinationLabel(destination.domain, destination.ip_address)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="From date" error={dateError}>
            {(id) => <TextInput id={id} type="date" value={draft.startDate} onChange={setField('startDate')} />}
          </Field>
          <Field label="To date">
            {(id) => <TextInput id={id} type="date" value={draft.endDate} onChange={setField('endDate')} />}
          </Field>
          <div className="flex items-end gap-2">
            <Button type="submit" variant="primary" icon={Search} disabled={Boolean(dateError)}>
              Search
            </Button>
            {hasFilters && (
              <Button variant="ghost" icon={X} onClick={clearFilters}>
                Clear
              </Button>
            )}
          </div>
        </form>

        <DataState
          result={result}
          isEmpty={(data) => data.items.length === 0}
          empty={{
            title: 'No network activity found',
            hint: hasFilters ? 'Try changing your filters.' : 'No events have been stored yet.',
          }}
          errorTitle="Unable to load network history"
        >
          {(data) => (
            <>
              <HistoryTable items={data.items} onSelect={(event) => setSelectedEvent(event.history_id)} />
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2 text-xs text-muted">
                <label className="flex items-center gap-2">
                  Rows per page
                  <Select
                    aria-label="Rows per page"
                    value={filters.pageSize}
                    onChange={(event) => update({ pageSize: event.target.value })}
                    className="h-7 w-20 text-xs"
                  >
                    {['25', '50', '100'].map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </Select>
                </label>
              </div>
              <Pagination data={data} onPageChange={(next) => update({ page: next })} />
            </>
          )}
        </DataState>
      </Card>

      {selectedEvent !== null && <EventDrawer eventId={selectedEvent} onClose={() => setSelectedEvent(null)} />}
    </>
  )
}
