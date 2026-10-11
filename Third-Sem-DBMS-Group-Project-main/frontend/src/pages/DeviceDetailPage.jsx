import { Activity, ChevronLeft, Globe } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ActivityChart } from '../components/charts/ActivityChart.jsx'
import { HistoryPanel } from '../components/HistoryPanel.jsx'
import { Card, CardHeader } from '../components/ui/Card.jsx'
import { DestinationName, DetailList, KpiCard, PageHeader } from '../components/ui/Misc.jsx'
import { DataState, EmptyState, SkeletonBlock } from '../components/ui/States.jsx'
import { Badge, StatusBadge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { getDevice, getDeviceHistory } from '../services/devices.js'
import { formatDateTime, formatNumber, relativeTime } from '../utils/format.js'
import { titleCase } from '../utils/status.js'

function DeviceBody({ device }) {
  const navigate = useNavigate()

  return (
    <>
      <PageHeader
        breadcrumb={
          <Link to="/devices" className="inline-flex items-center gap-1 hover:text-ink">
            <ChevronLeft size={12} aria-hidden="true" /> Devices
          </Link>
        }
        title={device.device_identifier}
        subtitle={device.device_name ?? `Observed through ${device.node_name}`}
      />

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard label="Status" value={<StatusBadge status={device.status} />} />
        <KpiCard label="Stored events" value={formatNumber(device.total_events)} icon={Activity} />
        <KpiCard label="First seen" value={<span className="text-base">{relativeTime(device.first_seen)}</span>} hint={formatDateTime(device.first_seen)} />
        <KpiCard label="Last seen" value={<span className="text-base">{relativeTime(device.last_seen)}</span>} hint={formatDateTime(device.last_seen)} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Device details" />
          <div className="p-4">
            <DetailList
              items={[
                { label: 'Identifier', value: device.device_identifier, mono: true },
                { label: 'Name', value: device.device_name },
                { label: 'IP address', value: device.ip_address, mono: true },
                { label: 'MAC address', value: device.mac_address, mono: true },
                { label: 'Hostname', value: device.hostname, mono: true },
                {
                  label: 'Node',
                  value: (
                    <Link to={`/nodes/${device.node_id}`} className="text-accent hover:underline">
                      {device.node_name}
                    </Link>
                  ),
                },
              ]}
            />
            <p className="mt-3 text-xs text-faint">
              Details that were not observed are shown as “—” rather than guessed. The IP address can change while
              the device stays the same.
            </p>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Activity, last 7 days" subtitle="Stored events per day" icon={Activity} />
          {device.total_events === 0 ? (
            <EmptyState title="No activity yet" hint="No events have been stored for this device." />
          ) : (
            <ActivityChart points={device.activity_by_day} bucket="day" height={220} />
          )}
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Recent destinations" subtitle="Most recently visited first" icon={Globe} />
        {device.recent_destinations.length === 0 ? (
          <EmptyState title="No destinations yet" hint="This device has not reached any destination." />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Destination</Th>
                  <Th>IP</Th>
                  <Th>Category</Th>
                  <Th align="right">Visits</Th>
                  <Th>Last visit</Th>
                </tr>
              </thead>
              <tbody>
                {device.recent_destinations.map((destination) => (
                  <Tr key={destination.destination_id} onClick={() => navigate(`/destinations/${destination.destination_id}`)}>
                    <Td>
                      <DestinationName domain={destination.domain} ip={destination.ip_address} />
                    </Td>
                    <Td mono>{destination.ip_address}</Td>
                    <Td>
                      <Badge>{titleCase(destination.category)}</Badge>
                    </Td>
                    <Td align="right">{formatNumber(destination.visits)}</Td>
                    <Td className="whitespace-nowrap text-muted">{formatDateTime(destination.last_visit)}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <div className="mt-4">
        <HistoryPanel
          title="Network history"
          hide={['device']}
          load={(params, signal) => getDeviceHistory(device.device_id, params, signal)}
        />
      </div>
    </>
  )
}

export default function DeviceDetailPage() {
  const { id } = useParams()
  const result = useAsync((signal) => getDevice(id, signal), [id])
  return (
    <DataState
      result={result}
      skeleton={
        <Card>
          <SkeletonBlock height={320} />
        </Card>
      }
      errorTitle="Unable to load this device"
      backTo={{ to: '/devices', label: 'Back to devices' }}
    >
      {(device) => <DeviceBody key={device.device_id} device={device} />}
    </DataState>
  )
}
