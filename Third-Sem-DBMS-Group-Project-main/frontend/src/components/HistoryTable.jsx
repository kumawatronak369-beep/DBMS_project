import { formatDateTime, formatPort, formatTime } from '../utils/format.js'
import { DestinationName, Mono } from './ui/Misc.jsx'
import { Badge } from './ui/StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from './ui/Table.jsx'

export function HistoryTable({ items, onSelect, variant = 'full', hide = [] }) {
  const compact = variant === 'compact'
  const show = (column) => !hide.includes(column)

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>Time</Th>
            {show('device') && <Th>Device</Th>}
            {!compact && show('device') && <Th>IP</Th>}
            {show('node') && <Th>Node</Th>}
            <Th>{compact ? 'Destination' : 'Destination IP'}</Th>
            {!compact && <Th>Domain</Th>}
            {!compact && <Th>Protocol</Th>}
            {!compact && <Th align="right" className="hidden md:table-cell">Source port</Th>}
            {!compact && <Th align="right">Destination port</Th>}
          </tr>
        </thead>
        <tbody>
          {items.map((event) => (
            <Tr key={event.history_id} onClick={onSelect ? () => onSelect(event) : undefined}>
              <Td mono className="whitespace-nowrap">
                {compact ? formatTime(event.observed_at) : formatDateTime(event.observed_at)}
              </Td>
              {show('device') && <Td className="whitespace-nowrap font-medium">{event.device_identifier}</Td>}
              {!compact && show('device') && (
                <Td mono>{event.device_ip}</Td>
              )}
              {show('node') && (
                <Td className="whitespace-nowrap text-muted" >
                  {event.node_code}
                </Td>
              )}
              <Td className="whitespace-nowrap">
                {compact ? <DestinationName domain={event.domain} ip={event.destination_ip} /> : <Mono>{event.destination_ip}</Mono>}
                {compact && Number.isInteger(event.destination_port) && (
                  <span className="ml-1.5 font-mono text-xs text-faint">
                    {event.destination_port}
                    {event.protocol ? `/${event.protocol}` : ''}
                  </span>
                )}
              </Td>
              {!compact && <Td className="whitespace-nowrap">{event.domain ?? <span className="text-faint">—</span>}</Td>}
              {!compact && (
                <Td className="whitespace-nowrap">{event.protocol ? <Badge>{event.protocol}</Badge> : <span className="text-faint">—</span>}</Td>
              )}
              {!compact && (
                <Td mono align="right" className="hidden md:table-cell">
                  {formatPort(event.source_port)}
                </Td>
              )}
              {!compact && (
                <Td mono align="right">
                  {formatPort(event.destination_port)}
                </Td>
              )}
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  )
}
