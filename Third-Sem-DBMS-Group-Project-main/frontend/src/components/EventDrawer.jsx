import { Link } from 'react-router-dom'
import { getHistoryEvent } from '../services/history.js'
import { useAsync } from '../hooks/useAsync.js'
import { formatDateTime, formatPort, relativeTime } from '../utils/format.js'
import { titleCase } from '../utils/status.js'
import { Badge } from './ui/StatusBadge.jsx'
import { DetailList } from './ui/Misc.jsx'
import { DataState, SkeletonRows } from './ui/States.jsx'
import { Drawer } from './ui/Modal.jsx'

const linkClass = 'text-accent underline-offset-2 hover:underline'

export function EventDrawer({ eventId, onClose }) {
  const result = useAsync((signal) => getHistoryEvent(eventId, signal), [eventId])

  return (
    <Drawer title={`Event #${eventId}`} onClose={onClose}>
      <DataState result={result} skeleton={<SkeletonRows rows={8} />} errorTitle="Unable to load this event">
        {(event) => (
          <div className="space-y-5 p-4">
            <div>
              <p className="text-xs text-muted">Observed</p>
              <p className="mt-0.5 text-base font-medium text-ink">{formatDateTime(event.observed_at)}</p>
              <p className="text-xs text-faint">{relativeTime(event.observed_at)}</p>
            </div>

            <section>
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">Device</h3>
              <DetailList
                items={[
                  {
                    label: 'Identifier',
                    value: (
                      <Link to={`/devices/${event.device_id}`} className={linkClass} onClick={onClose}>
                        {event.device_identifier}
                      </Link>
                    ),
                  },
                  { label: 'Name', value: event.device_name },
                  { label: 'IP address', value: event.device_ip, mono: true },
                ]}
              />
            </section>

            <section>
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">Observation point</h3>
              <DetailList
                items={[
                  {
                    label: 'Node',
                    value: (
                      <Link to={`/nodes/${event.node_id}`} className={linkClass} onClick={onClose}>
                        {event.node_name}
                      </Link>
                    ),
                  },
                  { label: 'Code', value: event.node_code, mono: true },
                ]}
              />
            </section>

            <section>
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">Destination</h3>
              <DetailList
                items={[
                  {
                    label: 'Domain',
                    value: event.domain ? (
                      <Link to={`/destinations/${event.destination_id}`} className={linkClass} onClick={onClose}>
                        {event.domain}
                      </Link>
                    ) : (
                      <span className="text-muted">Not observed</span>
                    ),
                  },
                  {
                    label: 'IP address',
                    value: (
                      <Link to={`/destinations/${event.destination_id}`} className={`font-mono ${linkClass}`} onClick={onClose}>
                        {event.destination_ip}
                      </Link>
                    ),
                  },
                  { label: 'Category', value: <Badge>{titleCase(event.category)}</Badge> },
                ]}
              />
              <p className="mt-2 text-xs text-faint">
                Category is descriptive application metadata, not a security classification.
              </p>
            </section>

            <section>
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">Connection</h3>
              <DetailList
                items={[
                  { label: 'Protocol', value: event.protocol ? <Badge>{event.protocol}</Badge> : null },
                  { label: 'Source port', value: event.source_port == null ? null : formatPort(event.source_port), mono: true },
                  { label: 'Destination port', value: event.destination_port == null ? null : formatPort(event.destination_port), mono: true },
                ]}
              />
              <p className="mt-2 text-xs text-faint">
                Shown only when the collector could observe the connection; otherwise a dash.
              </p>
            </section>
          </div>
        )}
      </DataState>
    </Drawer>
  )
}
