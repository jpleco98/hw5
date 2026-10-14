import type { AgentName, Ticket } from '../api'
import { AGENTS, AGENT_ORDER, argLine, verb, type TableView } from '../agents'

const MOOD_LABEL = {
  idle: 'not needed yet',
  thinking: 'thinking…',
  tool: '',
  waiting: 'waiting on a teammate',
  done: 'done',
  error: 'hit a problem',
} as const

interface Props {
  view: TableView
  ticket: Ticket | null
  live: boolean
}

/** The five agents seated around one table, with hand-off wires drawn between them. */
export function RoundTable({ view, ticket, live }: Props) {
  const touched = (a: AgentName) => view.seats[a].mood !== 'idle'
  return (
    <div className={`table-room ${live ? 'is-live' : ''}`}>
      <svg className="wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        {view.wires.map((w, i) => {
          const a = AGENTS[w.from].seat
          const b = AGENTS[w.to].seat
          const mx = (a.x + b.x) / 2 + (b.y - a.y) * 0.18
          const my = (a.y + b.y) / 2 - (b.x - a.x) * 0.18
          return (
            <path
              key={i}
              d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
              className={`wire ${w.done ? 'wire-done' : 'wire-live'}`}
              pathLength={1}
              vectorEffect="non-scaling-stroke"
            />
          )
        })}
      </svg>

      <div className="tabletop" aria-hidden>
        {ticket ? (
          <div className="tabletop-slip">
            <span>No. {ticket.ticket_id}</span>
            <strong>{ticket.subject}</strong>
            <em>{ticket.requester}</em>
          </div>
        ) : (
          <div className="tabletop-slip empty">pick a ticket from the rail</div>
        )}
      </div>

      {AGENT_ORDER.map((a) => {
        const meta = AGENTS[a]
        const s = view.seats[a]
        const isActive = view.active === a && live
        return (
          <div
            key={a}
            className={`seat mood-${s.mood} ${isActive ? 'is-active' : ''} ${touched(a) ? '' : 'is-idle'} ${meta.seat.flip ? 'flip' : ''}`}
            style={{
              ...(meta.seat.flip
                ? { right: `calc(${100 - meta.seat.x}% - 23px)` }
                : { left: `calc(${meta.seat.x}% - 23px)` }),
              top: `calc(${meta.seat.y}% - 23px)`,
              ['--agent' as string]: meta.color,
            }}
          >
            <div className={`badge badge-${a}`}>{meta.initials}</div>
            <div className="seat-card">
              <div className="seat-name">
                {meta.name}
                {s.mood === 'done' && <span className="tick" aria-label="done">✓</span>}
              </div>
              <div className="seat-doing">
                {s.tool ? (
                  <>
                    <span className="doing-verb">{verb(s.tool.tool)}</span>
                    {argLine(s.tool) && <code>{argLine(s.tool)}</code>}
                  </>
                ) : (
                  <span className="doing-verb">{touched(a) ? MOOD_LABEL[s.mood] : meta.role}</span>
                )}
              </div>
              {s.said && <p className={`bubble ${meta.voice}`}>{clip(s.said, 150)}</p>}
            </div>
          </div>
        )
      })}

      <div className="meter">
        <span>{view.wires.length} hand-off{view.wires.length === 1 ? '' : 's'}</span>
        <span>{AGENT_ORDER.filter(touched).length} of 5 at the table</span>
        <span>{(view.tokens / 1000).toFixed(1)}k tokens</span>
      </div>
    </div>
  )
}

const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)
