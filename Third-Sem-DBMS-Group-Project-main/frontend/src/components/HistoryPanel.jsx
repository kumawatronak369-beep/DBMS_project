import { History } from 'lucide-react'
import { useState } from 'react'
import { useAsync } from '../hooks/useAsync.js'
import { EventDrawer } from './EventDrawer.jsx'
import { HistoryTable } from './HistoryTable.jsx'
import { Card, CardHeader } from './ui/Card.jsx'
import { RangeSelect } from './ui/Misc.jsx'
import { Pagination } from './ui/Pagination.jsx'
import { DataState, SkeletonRows } from './ui/States.jsx'

const RANGES = [
  { value: '24h', label: '24 hours' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: 'all', label: 'All time' },
]

export function HistoryPanel({ title = 'Network history', load, hide = [], pageSize = 10, defaultRange = 'all' }) {
  const [range, setRange] = useState(defaultRange)
  const [page, setPage] = useState(1)
  const [selectedEvent, setSelectedEvent] = useState(null)

  const result = useAsync(
    (signal) => load({ range: range === 'all' ? undefined : range, page, pageSize }, signal),
    [range, page, pageSize],
  )

  return (
    <Card>
      <CardHeader
        title={title}
        subtitle="Newest first. Select an event for details"
        icon={History}
        actions={
          <RangeSelect
            value={range}
            options={RANGES}
            onChange={(next) => {
              setRange(next)
              setPage(1)
            }}
          />
        }
      />
      <DataState
        result={result}
        skeleton={<SkeletonRows rows={6} />}
        isEmpty={(data) => data.items.length === 0}
        empty={{
          title: 'No network activity found',
          hint: range === 'all' ? 'No events have been stored yet.' : 'Try a longer time range.',
        }}
        errorTitle="Unable to load network history"
      >
        {(data) => (
          <>
            <HistoryTable items={data.items} hide={hide} onSelect={(event) => setSelectedEvent(event.history_id)} />
            <Pagination data={data} onPageChange={setPage} />
          </>
        )}
      </DataState>
      {selectedEvent !== null && <EventDrawer eventId={selectedEvent} onClose={() => setSelectedEvent(null)} />}
    </Card>
  )
}
