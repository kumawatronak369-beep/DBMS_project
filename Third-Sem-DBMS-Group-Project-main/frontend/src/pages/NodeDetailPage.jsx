import { Activity, ChevronLeft, MonitorSmartphone, Pencil, Power, PowerOff } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ActivityChart } from '../components/charts/ActivityChart.jsx'
import { EventDrawer } from '../components/EventDrawer.jsx'
import { ConfirmModal } from '../components/forms/ConfirmModal.jsx'
import { NodeFormModal } from '../components/forms/NodeFormModal.jsx'
import { HistoryTable } from '../components/HistoryTable.jsx'
import { Button } from '../components/ui/Button.jsx'
import { Card, CardHeader } from '../components/ui/Card.jsx'
import { DetailList, KpiCard, PageHeader } from '../components/ui/Misc.jsx'
import { DataState, EmptyState, SkeletonBlock, SkeletonRows } from '../components/ui/States.jsx'
import { StatusBadge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useAuth } from '../hooks/useAuth.js'
import { listDevices } from '../services/devices.js'
import { getNode, setNodeStatus } from '../services/nodes.js'
import { formatDateTime, formatNumber, relativeTime } from '../utils/format.js'

function NodeBody({ node, reload, isAdmin }) {
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const devices = useAsync((signal) => listDevices({ nodeId: node.node_id, pageSize: 8 }, signal), [node.node_id])
  const inactive = node.status === 'INACTIVE'

  return (
    <>
      <PageHeader
        breadcrumb={
          <Link to="/nodes" className="inline-flex items-center gap-1 hover:text-ink">
            <ChevronLeft size={12} aria-hidden="true" /> Nodes
          </Link>
        }
        title={node.node_name}
        subtitle={`${node.node_code} · ${node.location}`}
        actions={
          isAdmin && (
            <>
              <Button icon={Pencil} onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button
                icon={inactive ? Power : PowerOff}
                variant={inactive ? 'secondary' : 'danger'}
                onClick={() => setToggling(true)}
              >
                {inactive ? 'Enable' : 'Disable'}
              </Button>
            </>
          )
        }
      />

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard label="Status" value={<StatusBadge status={node.status} />} />
        <KpiCard label="Devices" value={formatNumber(node.device_count)} icon={MonitorSmartphone} />
        <KpiCard label="Stored events" value={formatNumber(node.event_count)} icon={Activity} />
        <KpiCard label="Last seen" value={<span className="text-base">{relativeTime(node.last_seen)}</span>} hint={formatDateTime(node.last_seen)} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Basic information" />
          <div className="p-4">
            <DetailList
              items={[
                { label: 'Node code', value: node.node_code, mono: true },
                { label: 'Name', value: node.node_name },
                { label: 'IP address', value: node.ip_address, mono: true },
                { label: 'Location', value: node.location },
                { label: 'Description', value: node.description },
                { label: 'Registered', value: formatDateTime(node.registered_at) },
                { label: 'Last seen', value: formatDateTime(node.last_seen) },
              ]}
            />
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Activity, last 7 days" subtitle="Stored events per day" icon={Activity} />
          {node.event_count === 0 ? (
            <EmptyState title="No activity yet" hint="No events have been stored for this node." />
          ) : (
            <ActivityChart points={node.activity_by_day} bucket="day" height={220} />
          )}
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader
            title="Devices"
            icon={MonitorSmartphone}
            actions={<Link to={`/devices?nodeId=${node.node_id}`} className="text-xs text-accent hover:underline">View all</Link>}
          />
          <DataState
            result={devices}
            skeleton={<SkeletonRows rows={4} />}
            isEmpty={(data) => data.items.length === 0}
            empty={{ title: 'No devices yet', hint: 'Devices appear when this node reports events.' }}
          >
            {(data) => (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>Device</Th>
                      <Th>IP</Th>
                      <Th>Status</Th>
                      <Th>Last seen</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((device) => (
                      <Tr key={device.device_id} onClick={() => navigate(`/devices/${device.device_id}`)}>
                        <Td className="font-medium">{device.device_identifier}</Td>
                        <Td mono>{device.ip_address}</Td>
                        <Td>
                          <StatusBadge status={device.status} />
                        </Td>
                        <Td className="whitespace-nowrap text-muted">{relativeTime(device.last_seen)}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            )}
          </DataState>
        </Card>

        <Card>
          <CardHeader
            title="Recent activity"
            icon={Activity}
            actions={<Link to={`/history?nodeId=${node.node_id}`} className="text-xs text-accent hover:underline">Open history</Link>}
          />
          {node.recent_activity.length === 0 ? (
            <EmptyState title="No recent activity" hint="Events appear here as this node reports them." />
          ) : (
            <HistoryTable
              items={node.recent_activity}
              variant="compact"
              hide={['node']}
              onSelect={(event) => setSelectedEvent(event.history_id)}
            />
          )}
        </Card>
      </div>

      {editing && <NodeFormModal node={node} onClose={() => setEditing(false)} onSaved={reload} />}
      {toggling && (
        <ConfirmModal
          title={inactive ? `Enable ${node.node_name}?` : `Disable ${node.node_name}?`}
          message={
            inactive
              ? 'The node becomes Active again and its collectors can submit events.'
              : 'The node is marked Inactive and its collectors will be rejected. Its devices and history are preserved.'
          }
          confirmLabel={inactive ? 'Enable node' : 'Disable node'}
          danger={!inactive}
          onConfirm={async () => {
            await setNodeStatus(node.node_id, inactive ? 'ACTIVE' : 'INACTIVE')
            reload()
          }}
          onClose={() => setToggling(false)}
        />
      )}
      {selectedEvent !== null && <EventDrawer eventId={selectedEvent} onClose={() => setSelectedEvent(null)} />}
    </>
  )
}

export default function NodeDetailPage() {
  const { id } = useParams()
  const { isAdmin } = useAuth()
  const result = useAsync((signal) => getNode(id, signal), [id])

  return (
    <DataState
      result={result}
      skeleton={
        <Card>
          <SkeletonBlock height={320} />
        </Card>
      }
      errorTitle="Unable to load this node"
      backTo={{ to: '/nodes', label: 'Back to nodes' }}
    >
      {(node) => <NodeBody node={node} reload={result.reload} isAdmin={isAdmin} />}
    </DataState>
  )
}
