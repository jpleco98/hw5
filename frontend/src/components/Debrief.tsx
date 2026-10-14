import type { AgentName, Draft } from '../api'
import { AGENTS, AGENT_ORDER, verb, type TableView } from '../agents'

interface Props {
  view: TableView
  drafts: Draft[]
}

type Report = {
  summary?: string
  facts?: { label: string; value: string; source_tool: string }[]
  actions_taken?: string[]
  recommendation?: string
  blockers?: string[]
  decision?: string
  rationale?: string
  human_next_steps?: string[]
  risks?: string[]
  status?: string
}

/** After the run: one card per agent that sat down, in its own voice, with what it did. */
export function Debrief({ view, drafts }: Props) {
  const present = AGENT_ORDER.filter((a) => view.seats[a].mood !== 'idle')
  const benched = AGENT_ORDER.filter((a) => view.seats[a].mood === 'idle')
  if (!present.length) return null
  return (
    <section className="debrief">
      <header className="debrief-head">
        <h3>Debrief</h3>
        {benched.length > 0 && (
          <span className="benched">
            Not called this time: {benched.map((a) => AGENTS[a].name).join(', ')}
          </span>
        )}
      </header>
      <div className="debrief-grid">
        {present.map((a) => (
          <Card key={a} agent={a} view={view} drafts={drafts.filter((d) => d.author === a)} />
        ))}
      </div>
    </section>
  )
}

function Card({ agent, view, drafts }: { agent: AgentName; view: TableView; drafts: Draft[] }) {
  const m = AGENTS[agent]
  const s = view.seats[agent]
  const r = (s.report ?? {}) as Report
  const tools = Object.entries(s.tools).filter(([t]) => t !== 'final_result')
  return (
    <article className={`dcard dcard-${agent}`} style={{ ['--agent' as string]: m.color }}>
      <header>
        <span className={`dot badge-${agent}`}>{m.initials}</span>
        <div>
          <strong>{m.name}</strong>
          {s.calledBy && <small>called by {AGENTS[s.calledBy].name}</small>}
        </div>
        {s.mood !== 'done' && <span className="dcard-state">{s.mood === 'error' ? 'stopped' : 'still working'}</span>}
      </header>

      {agent === 'boss' ? (
        <div className={m.voice}>
          {r.decision ? <p className="memo-decision">{r.decision}</p> : <p className="muted">No final call yet.</p>}
          {r.rationale && <p className="memo-why">{r.rationale}</p>}
          {!!r.human_next_steps?.length && (
            <div className="memo-list">
              <span className="kicker">For you</span>
              <ul>{r.human_next_steps.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          )}
          {!!r.risks?.length && (
            <div className="memo-list risks">
              <span className="kicker">Watch out</span>
              <ul>{r.risks.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          )}
        </div>
      ) : (
        <div className={m.voice}>
          <p>{r.summary ?? s.said ?? 'Working…'}</p>
          {!!r.facts?.length && (
            <dl className="facts">
              {r.facts.slice(0, 6).map((f, i) => (
                <div key={i} title={`from ${f.source_tool}`}>
                  <dt>{f.label}</dt>
                  <dd>{f.value}</dd>
                </div>
              ))}
            </dl>
          )}
          {!!r.actions_taken?.length && (
            <ul className="actions">{r.actions_taken.map((x, i) => <li key={i}>{x}</li>)}</ul>
          )}
        </div>
      )}

      {drafts.map((d) => (
        <figure key={d.draft_id} className="letter">
          <figcaption>
            Draft #{d.draft_id} to {d.recipient} · <em>not sent</em>
          </figcaption>
          <p className="letter-subject">{d.subject}</p>
          <p className="letter-body">{d.body}</p>
        </figure>
      ))}

      <footer className="toolbelt">
        {s.handoffsTo.map((t) => (
          <span key={t} className="chip chip-handoff">→ {AGENTS[t].name}</span>
        ))}
        {tools
          .filter(([t]) => t !== 'delegate')
          .map(([t, n]) => (
            <span key={t} className="chip" title={t}>
              <b>{verb(t)}</b>
              {n > 1 && <i>×{n}</i>}
            </span>
          ))}
      </footer>
    </article>
  )
}
