import { Activity, Globe, MonitorSmartphone, Network } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivityChart } from '../components/charts/ActivityChart.jsx'
import { NodeActivityChart, TopDestinationsChart } from '../components/charts/BarCharts.jsx'
import { Card, CardHeader } from '../components/ui/Card.jsx'
import { Field, Select, TextInput } from '../components/ui/Fields.jsx'
import { DestinationName, PageHeader, RangeSelect } from '../components/ui/Misc.jsx'
import { DataState, EmptyState, SkeletonBlock, SkeletonRows } from '../components/ui/States.jsx'
import { Badge } from '../components/ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from '../components/ui/Table.jsx'
import { useAsync } from '../hooks/useAsync.js'
import { listNodes } from '../services/nodes.js'
import {
  getActivityByNode,
  getActivityOverTime,
  getTopDestinationsReport,
  getTopDevicesReport,
} from '../services/reports.js'
import { formatNumber } from '../utils/format.js'
import { titleCase } from '../utils/status.js'

const RANGE_OPTIONS = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'custom', label: 'Custom range' },
]

const LIMIT = 10

export default function ReportsPage() {
  const [mode, setMode] = useState('7d')
  const [custom, setCustom] = useState({ startDate: '', endDate: '' })
  const [nodeId, setNodeId] = useState('')

  const customInvalid = mode === 'custom' && (!custom.startDate || !custom.endDate || custom.startDate > custom.endDate)
  const params = mode === 'custom' ? { startDate: custom.startDate, endDate: custom.endDate } : { range: mode }
  const options = { enabled: !customInvalid }
  const key = JSON.stringify(params)

  const nodes = useAsync((signal) => listNodes({ pageSize: 100 }, signal), [])
  const overTime = useAsync((signal) => getActivityOverTime({ ...params, nodeId }, signal), [key, nodeId], options)
  const topDestinations = useAsync((signal) => getTopDestinationsReport({ ...params, limit: LIMIT }, signal), [key], options)
  const topDevices = useAsync((signal) => getTopDevicesReport({ ...params, limit: LIMIT }, signal), [key], options)
  const byNode = useAsync((signal) => getActivityByNode(params, signal), [key], options)

  const rangeText =
    mode === 'custom' ? (customInvalid ? 'choose a valid date range' : `${custom.startDate} to ${custom.endDate}`) : RANGE_OPTIONS.find((o) => o.value === mode).label.toLowerCase()

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Database-driven summaries of stored network activity"
        actions={<RangeSelect value={mode} onChange={setMode} options={RANGE_OPTIONS} />}
      />

      {mode === 'custom' && (
        <Card className="mb-4">
          <div className="flex flex-wrap items-end gap-3 p-3">
            <Field label="From date">
              {(id) => (
                <TextInput id={id} type="date" value={custom.startDate} onChange={(e) => setCustom((c) => ({ ...c, startDate: e.target.value }))} />
              )}
            </Field>
            <Field label="To date" error={customInvalid && custom.startDate && custom.endDate ? 'Start date is after the end date' : null}>
              {(id) => (
                <TextInput id={id} type="date" value={custom.endDate} onChange={(e) => setCustom((c) => ({ ...c, endDate: e.target.value }))} />
              )}
            </Field>
            {customInvalid && !(custom.startDate && custom.endDate) && (
              <p className="pb-1.5 text-xs text-muted">Pick both dates to run the reports.</p>
            )}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Activity over time"
          subtitle={`Stored events, ${rangeText}${overTime.data ? ` (per ${overTime.data.bucket})` : ''}`}
          icon={Activity}
          actions={
            <Select aria-label="Filter by node" value={nodeId} onChange={(event) => setNodeId(event.target.value)} className="h-7 w-44 text-xs">
              <option value="">All nodes</option>
              {nodes.data?.items.map((node) => (
                <option key={node.node_id} value={node.node_id}>
                  {node.node_name}
                </option>
              ))}
            </Select>
          }
        />
        {customInvalid ? (
          <EmptyState title="Choose a date range" hint="Pick a start and end date (start must not be after end)." />
        ) : (
          <DataState
            result={overTime}
            skeleton={<SkeletonBlock height={280} />}
            isEmpty={(data) => data.points.every((point) => point.event_count === 0)}
            empty={{ title: 'No activity in this period', hint: 'Try a different range or node.' }}
          >
            {(data) => <ActivityChart points={data.points} bucket={data.bucket} height={280} />}
          </DataState>
        )}
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Most visited destinations" subtitle={rangeText} icon={Globe} />
          {customInvalid ? null : (
            <DataState
              result={topDestinations}
              skeleton={<SkeletonRows rows={6} />}
              isEmpty={(data) => data.length === 0}
              empty={{ title: 'No destinations in this period' }}
            >
              {(rows) => (
                <>
                  <TopDestinationsChart rows={rows.slice(0, 6)} />
                  <TableWrap>
                    <Table>
                      <thead>
                        <tr>
                          <Th>Domain</Th>
                          <Th>Category</Th>
                          <Th align="right">Event count</Th>
                          <Th align="right">Unique devices</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row) => (
                          <Tr key={row.destination_id}>
                            <Td>
                              <Link to={`/destinations/${row.destination_id}`} className="hover:text-accent">
                                <DestinationName domain={row.domain} ip={row.ip_address} />
                              </Link>
                            </Td>
                            <Td>
                              <Badge>{titleCase(row.category)}</Badge>
                            </Td>
                            <Td align="right">{formatNumber(row.event_count)}</Td>
                            <Td align="right">{formatNumber(row.unique_devices)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                </>
              )}
            </DataState>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Most active devices" subtitle={rangeText} icon={MonitorSmartphone} />
            {customInvalid ? null : (
              <DataState
                result={topDevices}
                skeleton={<SkeletonRows rows={6} />}
                isEmpty={(data) => data.length === 0}
                empty={{ title: 'No device activity in this period' }}
              >
                {(rows) => (
                  <TableWrap>
                    <Table>
                      <thead>
                        <tr>
                          <Th>Device</Th>
                          <Th>Node</Th>
                          <Th align="right">Event count</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row) => (
                          <Tr key={row.device_id}>
                            <Td>
                              <Link to={`/devices/${row.device_id}`} className="font-medium hover:text-accent">
                                {row.device_identifier}
                              </Link>
                            </Td>
                            <Td className="text-muted">{row.node_name}</Td>
                            <Td align="right">{formatNumber(row.event_count)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                )}
              </DataState>
            )}
          </Card>

          <Card>
            <CardHeader title="Node activity" subtitle={rangeText} icon={Network} />
            {customInvalid ? null : (
              <DataState
                result={byNode}
                skeleton={<SkeletonBlock height={200} />}
                isEmpty={(data) => data.length === 0}
                empty={{ title: 'No nodes registered' }}
              >
                {(rows) => (
                  <>
                    <NodeActivityChart rows={rows} height={180} />
                    <TableWrap>
                      <Table>
                        <thead>
                          <tr>
                            <Th>Node</Th>
                            <Th align="right">Event count</Th>
                            <Th align="right">Unique devices</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((row) => (
                            <Tr key={row.node_id}>
                              <Td>
                                <Link to={`/nodes/${row.node_id}`} className="font-medium hover:text-accent">
                                  {row.node_name}
                                </Link>
                              </Td>
                              <Td align="right">{formatNumber(row.event_count)}</Td>
                              <Td align="right">{formatNumber(row.unique_devices)}</Td>
                            </Tr>
                          ))}
                        </tbody>
                      </Table>
                    </TableWrap>
                  </>
                )}
              </DataState>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}
