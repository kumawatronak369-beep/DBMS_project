import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatBucket, formatDateTime, formatNumber } from '../../utils/format.js'
import { ChartTooltip } from './ChartTooltip.jsx'
import { axisTick, CHART_COLORS } from './chartTheme.js'

export function ActivityChart({ points, bucket, height = 240 }) {
  const data = points.map((point) => ({
    time: point.bucket,
    label: formatBucket(point.bucket, bucket),
    count: point.event_count,
  }))

  return (
    <div style={{ height }} className="px-2 pt-4" role="img" aria-label="Network activity over time">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <AreaChart data={data} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={axisTick}
            tickLine={false}
            axisLine={{ stroke: CHART_COLORS.grid }}
            minTickGap={28}
            interval="preserveStartEnd"
          />
          <YAxis allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} width={44} />
          <Tooltip
            cursor={{ stroke: CHART_COLORS.cursor }}
            content={
              <ChartTooltip
                describe={(point) => ({
                  title: bucket === 'hour' ? formatDateTime(point.time) : formatBucket(point.time, 'day'),
                  rows: [['Events', formatNumber(point.count)]],
                })}
              />
            }
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke={CHART_COLORS.accent}
            strokeWidth={2}
            fill={CHART_COLORS.accent}
            fillOpacity={0.12}
            dot={false}
            activeDot={{ r: 4, fill: CHART_COLORS.accent, stroke: '#0b0f14' }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
