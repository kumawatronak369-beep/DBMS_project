export function ChartTooltip({ active, payload, describe }) {
  if (!active || !payload?.length) return null
  const { title, rows } = describe(payload[0].payload)
  return (
    <div className="rounded-md border border-line-strong bg-panel px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-medium text-ink">{title}</p>
      {rows.map(([label, value]) => (
        <p key={label} className="flex justify-between gap-4 text-muted">
          <span>{label}</span>
          <span className="tabular-nums text-ink">{value}</span>
        </p>
      ))}
    </div>
  )
}
