import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API_BASE, type AgentEvent, type Cash, type Health, type Job, type PaymentRequest, type Ticket, type TicketDetail } from './api'
import { AGENTS, buildView, latestRun, money } from './agents'
import { TicketRail } from './components/TicketRail'
import { RoundTable } from './components/RoundTable'
import { Transcript } from './components/Transcript'
import { Debrief } from './components/Debrief'
import { CashDrawer } from './components/CashDrawer'

interface Toast {
  id: number
  text: string
  tone: 'ok' | 'warn' | 'info'
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  // #ticket=102 in the URL opens that ticket (handy for links and screenshots).
  const [selected, setSelected] = useState<number | null>(() => {
    const m = location.hash.match(/ticket=(\d+)/)
    return m ? Number(m[1]) : null
  })
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [requests, setRequests] = useState<PaymentRequest[]>([])
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState(false)
  const [signer, setSignerState] = useState(() => localStorage.getItem('cc-signer') ?? '')
  const [toasts, setToasts] = useState<Toast[]>([])
  const [justResolved, setJustResolved] = useState<number | null>(null)
  const [dropped, setDropped] = useState<number | null>(null)
  const [replay, setReplay] = useState<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const [showArchive, setShowArchive] = useState(false)
  const [armReset, setArmReset] = useState(false)
  const since = useRef(-1)
  const cashRef = useRef<number | null>(null)

  const setSigner = (s: string) => {
    setSignerState(s)
    localStorage.setItem('cc-signer', s)
  }

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000)
  }, [])

  // ---- data loading -------------------------------------------------------------

  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, r] = await Promise.all([api.tickets(), api.cash(), api.requests()])
      setTickets(t)
      setCash(c)
      setRequests(r)
      setOffline(false)
      if (cashRef.current !== null && c.balance < cashRef.current) {
        setDropped(cashRef.current - c.balance)
        setTimeout(() => setDropped(null), 4000)
      }
      cashRef.current = c.balance
      setSelected((s) => s ?? t.find((x) => x.state !== 'resolved')?.ticket_id ?? t[0]?.ticket_id ?? null)
    } catch {
      setOffline(true)
    }
  }, [])

  const pollEvents = useCallback(async () => {
    try {
      const res = await api.events(since.current)
      if (res.events.length) setEvents((prev) => [...prev, ...res.events])
      since.current = res.next_since
    } catch {
      /* shown by the offline banner */
    }
  }, [])

  useEffect(() => {
    api.health().then(setHealth).catch(() => setOffline(true))
    refreshBoard()
    pollEvents()
  }, [refreshBoard, pollEvents])

  // Live loop: events every 1.2 s while a run is going, otherwise every 4 s; board every 4 s.
  const running = job?.status === 'queued' || job?.status === 'running'
  useEffect(() => {
    const ev = setInterval(pollEvents, running ? 1200 : 4000)
    const bd = setInterval(refreshBoard, running ? 2500 : 5000)
    return () => {
      clearInterval(ev)
      clearInterval(bd)
    }
  }, [running, pollEvents, refreshBoard])

  // Watch the current job until it finishes.
  useEffect(() => {
    if (!job || !running) return
    const t = setInterval(async () => {
      try {
        const j = await api.job(job.job_id)
        if (j.status === 'done' || j.status === 'failed') {
          setJob(j)
          await pollEvents()
          await refreshBoard()
          if (j.status === 'done') {
            setJustResolved(j.ticket_id)
            setTimeout(() => setJustResolved(null), 2500)
            const out = j.outcome as { payment_request_ids?: number[]; status?: string } | undefined
            const n = out?.payment_request_ids?.length ?? 0
            toast(
              `Ticket ${j.ticket_id} resolved by the team${n ? `: ${n} check${n > 1 ? 's' : ''} waiting for your signature` : ''}.`,
              'ok',
            )
          } else toast(`Ticket ${j.ticket_id}: the run stopped (${j.error}).`, 'warn')
        }
      } catch {
        /* keep polling */
      }
    }, 1500)
    return () => clearInterval(t)
  }, [job, running, pollEvents, refreshBoard, toast])

  // Ticket detail (drafts, requests) for the selected ticket.
  useEffect(() => {
    if (selected === null) return
    api.ticket(selected).then(setDetail).catch(() => setDetail(null))
  }, [selected, tickets, events.length])

  useEffect(() => {
    setReplay(null)
    setPlaying(false)
    setShowArchive(false)
    if (selected !== null) history.replaceState(null, '', `#ticket=${selected}`)
  }, [selected])

  // ---- derived view ---------------------------------------------------------------

  const ticket = tickets.find((t) => t.ticket_id === selected) ?? null
  const runEvents = useMemo(() => (selected === null ? [] : latestRun(events, selected)), [events, selected])
  const liveHere = running && job?.ticket_id === selected
  const hasToday = !!ticket && (ticket.state !== 'open' || liveHere)
  const showRun = hasToday || showArchive
  const shown = showRun ? (replay === null ? runEvents : runEvents.slice(0, replay)) : []
  const view = useMemo(() => buildView(shown), [shown])

  // Replay animation
  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => {
      setReplay((r) => {
        const next = (r ?? 0) + 1
        if (next >= runEvents.length) {
          setPlaying(false)
          return null
        }
        return next
      })
    }, 380)
    return () => clearInterval(t)
  }, [playing, runEvents.length])

  // ---- actions --------------------------------------------------------------------

  const start = useCallback(async () => {
    if (!ticket || running) return
    try {
      const j = await api.run(ticket.ticket_id)
      setJob({ ...j, status: 'running' })
      setReplay(null)
      setShowArchive(false)
      toast(`Ticket ${ticket.ticket_id} handed to Boss.`, 'info')
      refreshBoard()
    } catch (e) {
      toast(String((e as Error).message), 'warn')
    }
  }, [ticket, running, toast, refreshBoard])

  const approve = async (r: PaymentRequest) => {
    try {
      await api.approve(r.request_id, signer.trim())
      toast(`Paid ${money(r.amount)} to ${r.payee}. Signed by ${signer.trim()}.`, 'ok')
      setTimeout(refreshBoard, 900)
      return null
    } catch (e) {
      refreshBoard()
      return (e as Error).message
    }
  }

  const reject = async (r: PaymentRequest) => {
    try {
      await api.reject(r.request_id, signer.trim(), `Voided at the desk by ${signer.trim()}`)
      toast(`Check #${r.request_id} voided. No money moved.`, 'info')
      refreshBoard()
      return null
    } catch (e) {
      return (e as Error).message
    }
  }

  const reset = async () => {
    if (!armReset) {
      setArmReset(true)
      setTimeout(() => setArmReset(false), 3500)
      return
    }
    setArmReset(false)
    try {
      await api.reset()
      cashRef.current = null
      setJob(null)
      setSelected(null)
      await refreshBoard()
      toast('Fresh day: the working database is back to the original values.', 'info')
    } catch (e) {
      toast((e as Error).message, 'warn')
    }
  }

  // Keyboard: 1-3 pick a ticket, R runs it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      const n = Number(e.key)
      if (n >= 1 && n <= tickets.length) setSelected(tickets[n - 1].ticket_id)
      if (e.key.toLowerCase() === 'r') start()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [tickets, start])

  // ---- layout ---------------------------------------------------------------------

  const shopDate = cash?.as_of ? new Date(`${cash.as_of}T12:00:00`) : null
  const activeName = view.active ? AGENTS[view.active].name : null

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">CC</span>
          <div>
            <strong>Campus Customs</strong>
            <span>Back office · Chapel Street</span>
          </div>
        </div>

        {shopDate && (
          <div className="calendar" title="The shop's 'today' (desk.date_today): every overdue check uses this date">
            <span className="cal-dow">{shopDate.toLocaleDateString('en-US', { weekday: 'short' })}</span>
            <span className="cal-day">{shopDate.getDate()}</span>
            <span className="cal-mon">{shopDate.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}</span>
          </div>
        )}

        <div className="topbar-right">
          <span className={`presence ${offline ? 'off' : health?.agents_ready ? 'on' : 'warn'}`}>
            {offline
              ? `backend offline (${API_BASE})`
              : health?.agents_ready
                ? `team on shift · ${health.model}`
                : 'agents not configured'}
          </span>
          <button className={`btn-reset ${armReset ? 'armed' : ''}`} onClick={reset} disabled={running}>
            {armReset ? 'Click again to wipe the board' : 'Start a fresh day'}
          </button>
        </div>
      </header>

      {offline && (
        <div className="offline">
          Can't reach the backend at {API_BASE}. Start it from <code>HW 5/backend</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <div className="floor">
        <TicketRail tickets={tickets} selected={selected} onSelect={setSelected} justResolved={justResolved} />

        <main className="center">
          {ticket && (
            <section className="brief">
              <div className="brief-text">
                <span className="eyebrow">
                  Ticket {ticket.ticket_id} · {ticket.type.replaceAll('_', ' ')}
                </span>
                <h1>
                  {ticket.subject} <span>for {ticket.requester}</span>
                </h1>
                {ticket.notes && <p className="brief-note">“{ticket.notes}”</p>}
              </div>
              <div className="brief-cta">
                <button
                  className={`btn-run ${ticket.state === 'open' ? '' : 'secondary'}`}
                  onClick={start}
                  disabled={running || offline || !health?.agents_ready}
                >
                  {liveHere ? (
                    <>
                      <span className="spinner" /> {activeName ? `${activeName} has it` : 'Team at work'}
                    </>
                  ) : running ? (
                    `Team busy on ticket ${job?.ticket_id}`
                  ) : ticket.state === 'open' ? (
                    'Hand it to the team'
                  ) : (
                    'Run the team again'
                  )}
                </button>
                <span className="cta-sub">
                  {ticket.state === 'resolved'
                    ? ticket.pending_approvals
                      ? `Resolved by the team · ${ticket.pending_approvals} check${ticket.pending_approvals > 1 ? 's' : ''} need your signature →`
                      : `Resolved by the team · board status: ${ticket.status.replaceAll('_', ' ')}`
                    : liveHere
                      ? 'Watch the table. Agents light up as they work.'
                      : 'Boss reads it first and decides who else to call.'}
                </span>
              </div>
            </section>
          )}

          <RoundTable view={view} ticket={ticket} live={liveHere && replay === null} />

          {!showRun && runEvents.length > 0 && (
            <button className="archive-link" onClick={() => setShowArchive(true)}>
              This ticket hasn't been worked on today's board. Show the last archived run from the audit trail →
            </button>
          )}

          {showRun && runEvents.length > 0 && !liveHere && (
            <div className="scrubber">
              <button onClick={() => { setReplay(playing ? replay : 0); setPlaying(!playing) }}>
                {playing ? '❚❚ pause' : '▶ replay the run'}
              </button>
              <input
                type="range"
                min={1}
                max={runEvents.length}
                value={replay ?? runEvents.length}
                onChange={(e) => {
                  setPlaying(false)
                  const v = Number(e.target.value)
                  setReplay(v >= runEvents.length ? null : v)
                }}
                aria-label="Scrub through the run"
              />
              <span>
                step {replay ?? runEvents.length} / {runEvents.length}
              </span>
            </div>
          )}

          {view.failed && <div className="failed">The run stopped: {view.failed}</div>}

          {showRun && (
            <div className="center-split">
              <section className="pane">
                <h3>At the table</h3>
                <Transcript events={shown} follow={liveHere} />
              </section>
              <Debrief view={view} drafts={detail?.drafts ?? []} />
            </div>
          )}
        </main>

        <CashDrawer
          cash={cash}
          requests={requests}
          signer={signer}
          setSigner={setSigner}
          onApprove={approve}
          onReject={reject}
          busy={running}
          dropped={dropped}
        />
      </div>

      <div className="toasts" role="status">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  )
}
