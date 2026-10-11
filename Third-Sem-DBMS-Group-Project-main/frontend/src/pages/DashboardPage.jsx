import { Activity, Globe, History, MonitorSmartphone, Network, RefreshCw, Server, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivityChart } from '../components/charts/ActivityChart.jsx'
import { NodeActivityChart, TopDestinationsChart } from '../components/charts/BarCharts.jsx'
import { EventDrawer } from '../components/EventDrawer.jsx'
import { HealthList } from '../components/HealthIndicators.jsx'
import { HistoryTable } from '../components/HistoryTable.jsx'
import { Button } from '../components/ui/Button.jsx'
import { Card, CardHeader } from '../components/ui/Card.jsx'
import { KpiCard, PageHeader, RangeSelect } from '../components/ui/Misc.jsx'
import { DataState, SkeletonBlock, SkeletonRows } from '../components/ui/States.jsx'
import { StatusBadge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { useHealth } from '../hooks/useHealth.js'
import { getActivity, getSummary, getTopDestinations, getTopDevices } from '../services/dashboard.js'
import { listDevices } from '../services/devices.js'
import { listHistory } from '../services/history.js'
import { listNodes } from '../services/nodes.js'
import { getActivityByNode } from '../services/reports.js'
import { formatNumber, formatTime, relativeTime } from '../utils/format.js'

const POLL_MS = 15000
const RANGE_LABEL = { '24h': 'the last 24 hours', '7d': 'the last 7 days', '30d': 'the last 30 days' }

function LiveToggle({ live, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={live}
      title={live ? 'Auto-refreshing every 15 seconds' : 'Auto-refresh is off'}
      className="inline-flex h-8 items-center gap-2 rounded-md border border-line-strong bg-panel-2 px-3 text-xs font-medium text-ink transition-colors hover:bg-line"
    >
      <span className={`size-1.5 rounded-full ${live ? 'animate-pulse bg-ok motion-reduce:animate-none' : 'bg-faint'}`} aria-hidden="true" />
      {live ? 'Live' : 'Paused'}
    </button>
  )
}

function MostActiveDevices({ rows }) {
  const max = Math.max(...rows.map((row) => row.event_count), 1)
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Device</Th>
            <Th>Node</Th>
            <Th align="right">Events</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <Tr key={row.device_id}>
              <Td>
                <Link to={`/devices/${row.device_id}`} className="font-medium text-ink hover:text-accent">
                  {row.device_identifier}
                </Link>
                <div className="mt-1 h-1 w-full rounded bg-panel-2">
                  <div
                    className="h-1 rounded bg-accent/70"
                    style={{ width: `${Math.max(4, (row.event_count / max) * 100)}%` }}
                  />
                </div>
              </Td>
              <Td className="whitespace-nowrap text-muted">{row.node_name}</Td>
              <Td align="right">{formatNumber(row.event_count)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  )
}

function RecentlySeenDevices({ items }) {
  return (
    <ul className="divide-y divide-line/60">
      {items.map((device) => (
        <li key={device.device_id}>
          <Link
            to={`/devices/${device.device_id}`}
            className="flex items-center justify-between gap-3 px-4 py-2.5 transition-colors hover:bg-panel-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-ink">{device.device_identifier}</p>
              <p className="truncate text-xs text-muted">
                {device.node_name} · <span className="font-mono">{device.ip_address}</span>
              </p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <StatusBadge status={device.status} />
              <span className="text-[11px] text-faint">{relativeTime(device.last_seen)}</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function NodeStatusList({ items }) {
  return (
    <ul className="divide-y divide-line/60">
      {items.map((node) => (
        <li key={node.node_id}>
          <Link
            to={`/nodes/${node.node_id}`}
            className="flex items-center justify-between gap-3 px-4 py-2 transition-colors hover:bg-panel-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[13px] text-ink">{node.node_name}</p>
              <p className="text-xs text-faint">
                {node.device_count} devices · seen {relativeTime(node.last_seen)}
              </p>
            </div>
            <StatusBadge status={node.status} />
          </Link>
        </li>
      ))}
    </ul>
  )
}

export default function DashboardPage() {
  const [range, setRange] = useState('24h')
  const [live, setLive] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const poll = { pollMs: live ? POLL_MS : 0 }

  const summary = useAsync((signal) => getSummary(signal), [], poll)
  const activity = useAsync((signal) => getActivity({ range }, signal), [range], poll)
  const topDestinations = useAsync((signal) => getTopDestinations({ range, limit: 6 }, signal), [range], poll)
  const topDevices = useAsync((signal) => getTopDevices({ range, limit: 6 }, signal), [range], poll)
  const nodeActivity = useAsync((signal) => getActivityByNode({ range }, signal), [range], poll)
  const recent = useAsync((signal) => listHistory({ pageSize: 8 }, signal), [], poll)
  const nodes = useAsync((signal) => listNodes({ pageSize: 100 }, signal), [], poll)
  const devices = useAsync((signal) => listDevices({ pageSize: 6 }, signal), [], poll)
  const health = useHealth(POLL_MS)

  const updatedAt = useMemo(() => (summary.data ? new Date() : null), [summary.data])

  const all = [summary, activity, topDestinations, topDevices, nodeActivity, recent, nodes, devices]
  const refreshAll = () => {
    all.forEach((result) => result.reload())
    health.reload()
  }
  const refreshing = all.some((result) => result.loading)
  const summaryData = summary.data
  const staleError = all.find((result) => result.error && result.data !== null)?.error

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={updatedAt ? `Updated ${formatTime(updatedAt)}` : 'Live overview of monitored networks'}
        actions={
          <>
            <RangeSelect value={range} onChange={setRange} />
            <LiveToggle live={live} onToggle={() => setLive((value) => !value)} />
            <Button icon={RefreshCw} onClick={refreshAll} loading={refreshing && !live} aria-label="Refresh dashboard">
              Refresh
            </Button>
          </>
        }
      />

      {staleError && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warn/30 bg-warn/10 px-4 py-2.5 text-xs text-warn" role="status">
          <span>Showing the last data received. Refresh failed: {staleError.message}</span>
          <button type="button" onClick={refreshAll} className="font-medium underline underline-offset-2">
            Retry now
          </button>
        </div>
      )}

      {summary.error && summary.data === null && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">
          Unable to load the dashboard summary: {summary.error.message}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard
          label="Active nodes"
          value={formatNumber(summaryData?.active_nodes)}
          icon={Network}
          loading={!summaryData && !summary.error}
          hint={nodes.data ? `of ${nodes.data.total} registered` : undefined}
          to="/nodes"
        />
        <KpiCard
          label="Registered devices"
          value={formatNumber(summaryData?.registered_devices)}
          icon={MonitorSmartphone}
          loading={!summaryData && !summary.error}
          to="/devices"
        />
        <KpiCard
          label="Today's events"
          value={formatNumber(summaryData?.todays_events)}
          icon={Activity}
          loading={!summaryData && !summary.error}
          hint="Stored, after de-duplication"
          to="/history"
        />
        <KpiCard
          label="Known destinations"
          value={formatNumber(summaryData?.known_destinations)}
          icon={Globe}
          loading={!summaryData && !summary.error}
          to="/destinations"
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Network activity over time"
            subtitle={`Stored events per ${activity.data?.bucket ?? 'hour'}, ${RANGE_LABEL[range]}`}
            icon={Activity}
          />
          <DataState
            quiet
            result={activity}
            skeleton={<SkeletonBlock height={260} />}
            isEmpty={(data) => data.points.every((point) => point.event_count === 0)}
            empty={{ title: 'No activity in this period', hint: 'Try a longer time range.' }}
          >
            {(data) => <ActivityChart points={data.points} bucket={data.bucket} height={260} />}
          </DataState>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="System health" icon={ShieldCheck} />
            <div className="px-4 py-1">
              <HealthList health={health} />
            </div>
          </Card>
          <Card>
            <CardHeader title="Node status" icon={Server} actions={<Link to="/nodes" className="text-xs text-accent hover:underline">All nodes</Link>} />
            <DataState
              quiet
              result={nodes}
              skeleton={<SkeletonRows rows={4} />}
              isEmpty={(data) => data.items.length === 0}
              empty={{ title: 'No nodes registered' }}
            >
              {(data) => <NodeStatusList items={data.items} />}
            </DataState>
          </Card>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader title="Top destinations" subtitle={RANGE_LABEL[range]} icon={Globe} actions={<Link to="/destinations" className="text-xs text-accent hover:underline">View all</Link>} />
          <DataState
            quiet
            result={topDestinations}
            skeleton={<SkeletonBlock height={220} />}
            isEmpty={(data) => data.length === 0}
            empty={{ title: 'No destinations in this period' }}
          >
            {(data) => <TopDestinationsChart rows={data} />}
          </DataState>
        </Card>

        <Card>
          <CardHeader title="Activity by node" subtitle={RANGE_LABEL[range]} icon={Network} />
          <DataState
            quiet
            result={nodeActivity}
            skeleton={<SkeletonBlock height={220} />}
            isEmpty={(data) => data.length === 0}
            empty={{ title: 'No nodes registered' }}
          >
            {(data) => <NodeActivityChart rows={data} />}
          </DataState>
        </Card>

        <Card>
          <CardHeader title="Recently seen devices" icon={MonitorSmartphone} actions={<Link to="/devices" className="text-xs text-accent hover:underline">View all</Link>} />
          <DataState
            quiet
            result={devices}
            skeleton={<SkeletonRows rows={5} />}
            isEmpty={(data) => data.items.length === 0}
            empty={{ title: 'No devices registered' }}
          >
            {(data) => <RecentlySeenDevices items={data.items} />}
          </DataState>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent network activity"
            subtitle="Newest stored events. Select one for details"
            icon={History}
            actions={<Link to="/history" className="text-xs text-accent hover:underline">Open history</Link>}
          />
          <DataState
            quiet
            result={recent}
            skeleton={<SkeletonRows rows={6} />}
            isEmpty={(data) => data.items.length === 0}
            empty={{ title: 'No network activity yet', hint: 'Events appear here as collectors report them.' }}
          >
            {(data) => <HistoryTable items={data.items} variant="compact" onSelect={(event) => setSelectedEvent(event.history_id)} />}
          </DataState>
        </Card>

        <Card>
          <CardHeader title="Most active devices" subtitle={RANGE_LABEL[range]} icon={MonitorSmartphone} />
          <DataState
            quiet
            result={topDevices}
            skeleton={<SkeletonRows rows={6} />}
            isEmpty={(data) => data.length === 0}
            empty={{ title: 'No device activity in this period' }}
          >
            {(data) => <MostActiveDevices rows={data} />}
          </DataState>
        </Card>
      </div>

      {selectedEvent !== null && <EventDrawer eventId={selectedEvent} onClose={() => setSelectedEvent(null)} />}
    </>
  )
}
