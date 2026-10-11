import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { destinationLabel, formatNumber } from '../../utils/format.js'
import { ChartTooltip } from './ChartTooltip.jsx'
import { axisTick, CHART_COLORS } from './chartTheme.js'

export function TopDestinationsChart({ rows, height }) {
  const data = rows.map((row) => ({
    label: destinationLabel(row.domain, row.ip_address),
    count: row.event_count,
    devices: row.unique_devices,
    ip: row.ip_address,
  }))
  const chartHeight = height ?? Math.max(160, data.length * 34 + 24)

  return (
    <div style={{ height: chartHeight }} className="px-2 pt-3" role="img" aria-label="Top destinations by events">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} horizontal={false} />
          <XAxis type="number" allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={128}
            tick={{ ...axisTick, fill: '#c9d3df' }}
            tickLine={false}
            axisLine={false}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: 'rgb(255 255 255 / 0.04)' }}
            content={
              <ChartTooltip
                describe={(row) => ({
                  title: row.label,
                  rows: [
                    ['Events', formatNumber(row.count)],
                    ['Unique devices', formatNumber(row.devices)],
                    ['IP', row.ip],
                  ],
                })}
              />
            }
          />
          <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={16} isAnimationActive={false}>
            {data.map((row, index) => (
              <Cell key={row.label} fill={index === 0 ? CHART_COLORS.accent : '#2f5fb0'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function NodeActivityChart({ rows, height = 220 }) {
  const data = rows.map((row) => ({
    label: row.node_code,
    name: row.node_name,
    count: row.event_count,
    devices: row.unique_devices,
  }))

  return (
    <div style={{ height }} className="px-2 pt-4" role="img" aria-label="Events by node">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart data={data} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
          <XAxis dataKey="label" tick={axisTick} tickLine={false} axisLine={{ stroke: CHART_COLORS.grid }} interval={0} />
          <YAxis allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} width={44} />
          <Tooltip
            cursor={{ fill: 'rgb(255 255 255 / 0.04)' }}
            content={
              <ChartTooltip
                describe={(row) => ({
                  title: `${row.name} (${row.label})`,
                  rows: [
                    ['Events', formatNumber(row.count)],
                    ['Unique devices', formatNumber(row.devices)],
                  ],
                })}
              />
            }
          />
          <Bar dataKey="count" fill={CHART_COLORS.cyan} fillOpacity={0.85} radius={[3, 3, 0, 0]} maxBarSize={48} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
