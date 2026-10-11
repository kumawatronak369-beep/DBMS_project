import { Activity, ChevronLeft, MonitorSmartphone, Network } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { HistoryPanel } from '../components/HistoryPanel.jsx'
import { Card, CardHeader } from '../components/ui/Card.jsx'
import { DetailList, KpiCard, PageHeader } from '../components/ui/Misc.jsx'
import { DataState, EmptyState, SkeletonBlock } from '../components/ui/States.jsx'
import { Badge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { getDestination, getDestinationHistory } from '../services/destinations.js'
import { destinationLabel, formatDateTime, formatNumber, relativeTime } from '../utils/format.js'
import { titleCase } from '../utils/status.js'

function DestinationBody({ destination }) {
  const navigate = useNavigate()
  const maxNodeEvents = Math.max(...destination.nodes.map((node) => node.event_count), 1)

  return (
    <>
      <PageHeader
        breadcrumb={
          <Link to="/destinations" className="inline-flex items-center gap-1 hover:text-ink">
            <ChevronLeft size={12} aria-hidden="true" /> Destinations
          </Link>
        }
        title={destinationLabel(destination.domain, destination.ip_address)}
        subtitle={destination.domain ? destination.ip_address : 'No DNS name was observed for this destination'}
      />

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard label="Total events" value={formatNumber(destination.event_count)} icon={Activity} />
        <KpiCard label="Unique devices" value={formatNumber(destination.unique_devices)} icon={MonitorSmartphone} />
        <KpiCard label="Nodes" value={formatNumber(destination.nodes.length)} icon={Network} />
        <KpiCard label="Last seen" value={<span className="text-base">{relativeTime(destination.last_seen)}</span>} hint={formatDateTime(destination.last_seen)} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Destination details" />
          <div className="p-4">
            <DetailList
              items={[
                { label: 'Domain', value: destination.domain ?? 'Not observed' },
                { label: 'Destination IP', value: destination.ip_address, mono: true },
                { label: 'Category', value: <Badge>{titleCase(destination.category)}</Badge> },
                { label: 'First seen', value: formatDateTime(destination.first_seen) },
                { label: 'Last seen', value: formatDateTime(destination.last_seen) },
              ]}
            />
            <p className="mt-3 text-xs text-faint">
              The category is descriptive application metadata, not a security classification.
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader title="Associated nodes" subtitle="Where this destination was observed" icon={Network} />
          {destination.nodes.length === 0 ? (
            <EmptyState title="No nodes" hint="No node has reported this destination." />
          ) : (
            <ul className="divide-y divide-line/60">
              {destination.nodes.map((node) => (
                <li key={node.node_id}>
                  <Link to={`/nodes/${node.node_id}`} className="block px-4 py-2.5 transition-colors hover:bg-panel-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-[13px] text-ink">{node.node_name}</span>
                      <span className="text-xs tabular-nums text-muted">{formatNumber(node.event_count)} events</span>
                    </div>
                    <div className="mt-1.5 h-1 rounded bg-panel-2">
                      <div className="h-1 rounded bg-cyan/70" style={{ width: `${Math.max(4, (node.event_count / maxNodeEvents) * 100)}%` }} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Devices accessing this destination" subtitle="By number of accesses" icon={MonitorSmartphone} />
          {destination.devices.length === 0 ? (
            <EmptyState title="No devices" hint="No device has accessed this destination." />
          ) : (
            <div className="max-h-72 overflow-y-auto">
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>Device</Th>
                      <Th align="right">Accesses</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {destination.devices.map((device) => (
                      <Tr key={device.device_id} onClick={() => navigate(`/devices/${device.device_id}`)}>
                        <Td>
                          <p className="font-medium text-ink">{device.device_identifier}</p>
                          <p className="text-xs text-faint">
                            {device.node_name} · last {relativeTime(device.last_access)}
                          </p>
                        </Td>
                        <Td align="right">{formatNumber(device.access_count)}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4">
        <HistoryPanel
          title="Recent access"
          hide={[]}
          load={(params, signal) => getDestinationHistory(destination.destination_id, params, signal)}
        />
      </div>
    </>
  )
}

export default function DestinationDetailPage() {
  const { id } = useParams()
  const result = useAsync((signal) => getDestination(id, signal), [id])
  return (
    <DataState
      result={result}
      skeleton={
        <Card>
          <SkeletonBlock height={320} />
        </Card>
      }
      errorTitle="Unable to load this destination"
      backTo={{ to: '/destinations', label: 'Back to destinations' }}
    >
      {(destination) => <DestinationBody key={destination.destination_id} destination={destination} />}
    </DataState>
  )
}
