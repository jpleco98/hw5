import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../api'
import { AGENTS, argLine, verb } from '../agents'

interface Props {
  events: AgentEvent[]
  follow: boolean
}

/** The running conversation. Each agent writes in its own "hand" (see styles: voice-*). */
export function Transcript({ events, follow }: Props) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Scroll only the transcript box (not the page) so the table stays in view while it runs.
    if (follow && box.current) box.current.scrollTo({ top: box.current.scrollHeight, behavior: 'smooth' })
  }, [events.length, follow])

  const lines = events.filter((e) => e.event !== 'tool_results' || e.tool_results.some((r) => !r.ok))
  if (!lines.length) return <div className="transcript empty">Nothing said yet.</div>

  return (
    <div className="transcript" ref={box}>
      {lines.map((e) => {
        const m = AGENTS[e.agent]
        const time = new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        return (
          <div key={e.index} className={`line ev-${e.event}`} style={{ ['--agent' as string]: m.color, marginLeft: `${e.depth * 18}px` }}>
            <div className="line-who">
              <span className={`dot badge-${e.agent}`}>{m.initials}</span>
              <span className="who-name">{m.name}</span>
              <span className="who-time">{time}</span>
            </div>
            <div className={`line-body ${m.voice}`}>{renderBody(e)}</div>
          </div>
        )
      })}
    </div>
  )
}

function renderBody(e: AgentEvent) {
  switch (e.event) {
    case 'run_start':
      return (
        <p className="said">
          <span className="kicker">{e.depth === 0 ? 'Picked up the ticket' : 'Was handed'}</span>
          {e.depth === 0 ? '' : e.said?.replace(/^\[Ticket #\d+\] Task from [^:]+:\n?/, '')}
        </p>
      )
    case 'model_response':
      return (
        <>
          {e.said && <p className="said">{e.said}</p>}
          {e.delegations.map((d, i) => (
            <p key={i} className="handoff">
              <span className="kicker">Hands off to {AGENTS[d.to]?.name ?? d.to}</span>
              {d.task}
            </p>
          ))}
          <div className="chips">
            {e.tool_calls
              .filter((c) => c.tool !== 'delegate')
              .map((c, i) => (
                <span key={i} className={`chip ${c.tool === 'final_result' ? 'chip-final' : ''}`}>
                  <b>{c.tool === 'final_result' ? 'writes up the report' : verb(c.tool)}</b>
                  {argLine(c) && <i>{argLine(c)}</i>}
                </span>
              ))}
          </div>
        </>
      )
    case 'tool_results':
      return e.tool_results
        .filter((r) => !r.ok)
        .map((r, i) => (
          <p key={i} className="said warn">
            {r.tool} pushed back: {r.result}
          </p>
        ))
    case 'run_end': {
      const o = e.output ?? {}
      return (
        <p className="said final">
          <span className="kicker">{e.depth === 0 ? 'Final call' : 'Reports back'}</span>
          {String(o.decision ?? o.summary ?? e.said ?? '')}
        </p>
      )
    }
    case 'run_retry':
      return <p className="said warn">Thought too long; asked to give the short version.</p>
    case 'delegation_refused':
      return <p className="said warn">Guardrail: {e.said}</p>
    case 'run_error':
      return <p className="said warn">Error: {e.error ?? e.said}</p>
  }
}
