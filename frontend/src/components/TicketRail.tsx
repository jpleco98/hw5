import type { Ticket } from '../api'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price request',
}

const STATUS_LABEL: Record<string, string> = {
  open: 'open',
  in_progress: 'in progress',
  waiting_on_approval: 'waiting on you',
  waiting_on_vendor: 'waiting on vendor',
  resolved: 'resolved',
}

interface Props {
  tickets: Ticket[]
  selected: number | null
  onSelect: (id: number) => void
  justResolved: number | null
}

/** The order rail: paper tickets clipped to a steel bar, like a kitchen pass. */
export function TicketRail({ tickets, selected, onSelect, justResolved }: Props) {
  const open = tickets.filter((t) => t.state !== 'resolved').length
  return (
    <aside className="rail">
      <div className="rail-head">
        <span className="eyebrow">The rail</span>
        <span className="rail-count">
          {open} of {tickets.length} still open
        </span>
      </div>
      <div className="rail-bar" aria-hidden />
      <ol className="rail-tickets">
        {tickets.map((t, i) => (
          <li key={t.ticket_id}>
            <button
              className={`slip state-${t.state} ${selected === t.ticket_id ? 'is-selected' : ''}`}
              style={{ ['--tilt' as string]: `${[-1.2, 0.8, -0.4][i % 3]}deg` }}
              onClick={() => onSelect(t.ticket_id)}
              aria-pressed={selected === t.ticket_id}
              title={`Ticket ${t.ticket_id} (press ${i + 1})`}
            >
              <span className="clip" aria-hidden />
              <span className="slip-top">
                <span className="slip-no">No. {t.ticket_id}</span>
                <span className="slip-type">{TYPE_LABEL[t.type] ?? t.type}</span>
              </span>
              <span className="slip-subject">{t.subject}</span>
              <span className="slip-from">from {t.requester}</span>
              {t.sku && (
                <span className="slip-item">
                  {t.sku} · {t.size} × {t.qty}
                </span>
              )}
              {t.notes && <span className="slip-note">“{t.notes}”</span>}
              <span className="slip-foot">
                <span className={`pill status-${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
                {t.pending_approvals > 0 && (
                  <span className="pill pill-you">
                    {t.pending_approvals} check{t.pending_approvals > 1 ? 's' : ''} to sign
                  </span>
                )}
              </span>
              {t.state === 'running' && <span className="working">team at work</span>}
              {t.state === 'resolved' && (
                <span className={`stamp ${justResolved === t.ticket_id ? 'stamp-in' : ''}`}>Resolved</span>
              )}
            </button>
          </li>
        ))}
      </ol>
      <p className="rail-hint">Keys 1–3 pick a ticket · R hands it to the team</p>
    </aside>
  )
}
