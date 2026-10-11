import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button.jsx'
import { Card } from '../components/ui/Card.jsx'
import { SearchInput, Select } from '../components/ui/Fields.jsx'
import { DestinationName, PageHeader } from '../components/ui/Misc.jsx'
import { Pagination } from '../components/ui/Pagination.jsx'
import { DataState } from '../components/ui/States.jsx'
import { Badge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useDebounce } from '../hooks/useDebounce.js'
import { useUrlState } from '../hooks/useUrlState.js'
import { listDestinations } from '../services/destinations.js'
import { formatDateTime, formatNumber, relativeTime } from '../utils/format.js'
import { DESTINATION_CATEGORIES, titleCase } from '../utils/status.js'

const DEFAULTS = { search: '', category: '', page: '1' }
const PAGE_SIZE = 25

export default function DestinationsPage() {
  const navigate = useNavigate()
  const [filters, update] = useUrlState(DEFAULTS)
  const [text, setText] = useState(filters.search)
  const debouncedText = useDebounce(text, 300)

  useEffect(() => {
    if (debouncedText !== filters.search) update({ search: debouncedText })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedText])

  const page = Number(filters.page) || 1
  const result = useAsync(
    (signal) => listDestinations({ search: filters.search, category: filters.category, page, pageSize: PAGE_SIZE }, signal),
    [filters.search, filters.category, page],
  )
  const hasFilters = Boolean(filters.search || filters.category)

  return (
    <>
      <PageHeader title="Destinations" subtitle="Network destinations observed by collectors" />

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <SearchInput
            value={text}
            onChange={setText}
            placeholder="Search domain or IP address"
            label="Search destinations"
            className="w-full sm:w-72"
          />
          <Select
            aria-label="Filter by category"
            value={filters.category}
            onChange={(event) => update({ category: event.target.value })}
            className="w-44"
          >
            <option value="">All categories</option>
            {DESTINATION_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {titleCase(category)}
              </option>
            ))}
          </Select>
          {hasFilters && (
            <Button
              variant="ghost"
              onClick={() => {
                setText('')
                update({ search: '', category: '' })
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
            title: hasFilters ? 'No destinations match your filters' : 'No destinations found',
            hint: hasFilters ? 'Try changing or clearing the filters.' : 'Destinations appear as collectors report activity.',
          }}
          errorTitle="Unable to load destinations"
        >
          {(data) => (
            <>
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>Destination</Th>
                      <Th>IP address</Th>
                      <Th>Category</Th>
                      <Th align="right">Events</Th>
                      <Th align="right">Devices</Th>
                      <Th>First seen</Th>
                      <Th>Last seen</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((destination) => (
                      <Tr key={destination.destination_id} onClick={() => navigate(`/destinations/${destination.destination_id}`)}>
                        <Td className="font-medium">
                          <DestinationName domain={destination.domain} ip={destination.ip_address} />
                        </Td>
                        <Td mono>{destination.ip_address}</Td>
                        <Td>
                          <Badge>{titleCase(destination.category)}</Badge>
                        </Td>
                        <Td align="right">{formatNumber(destination.event_count)}</Td>
                        <Td align="right">{formatNumber(destination.unique_devices)}</Td>
                        <Td className="whitespace-nowrap text-muted">{formatDateTime(destination.first_seen)}</Td>
                        <Td className="whitespace-nowrap">
                          <span title={formatDateTime(destination.last_seen)}>{relativeTime(destination.last_seen)}</span>
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
        <p className="border-t border-line px-4 py-2 text-xs text-faint">
          Categories are descriptive application metadata, not a security classification.
        </p>
      </Card>
    </>
  )
}
