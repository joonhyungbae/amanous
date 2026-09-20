import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { GROUPS, LINKS, TRACKS } from './data/tracks'
import './App.css'

const BASE = import.meta.env.BASE_URL
const ORDER = GROUPS.flatMap((g) => g.tracks)
const SECTION_HUES = [38, 205, 150, 330, 270, 15]

function clock(s) {
  if (!Number.isFinite(s)) return '0:00'
  const t = Math.max(0, Math.floor(s))
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}

function hueFor(symbols, symbol) {
  const i = Math.max(0, Object.keys(symbols).indexOf(symbol))
  return SECTION_HUES[i % SECTION_HUES.length]
}

/** Piano roll drawn once per size change. The playhead is a separate element, so playback costs no redraw. */
function PianoRoll({ data, symbols }) {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !data) return undefined
    const draw = () => {
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      const ctx = canvas.getContext('2d')
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, w, h)
      const dark = window.matchMedia('(prefers-color-scheme: dark)').matches
      const [lo, hi] = data.key_range
      const span = Math.max(12, hi - lo)
      const noteH = Math.max(1.5, Math.min(4, h / span))
      for (const s of data.sections) {
        const x0 = (s.start / data.duration) * w
        const x1 = (s.end / data.duration) * w
        ctx.fillStyle = `hsla(${hueFor(symbols, s.symbol)}, 60%, 50%, ${dark ? 0.1 : 0.09})`
        ctx.fillRect(x0, 0, x1 - x0, h)
      }
      for (const [t, key, vel] of data.notes) {
        const x = (t / data.duration) * w
        const y = h - ((key - lo) / span) * (h - noteH) - noteH
        const a = 0.25 + 0.75 * (vel / 127)
        ctx.fillStyle = dark ? `rgba(240, 232, 214, ${a})` : `rgba(38, 32, 20, ${a})`
        ctx.fillRect(x, y, 1.6, noteH)
      }
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    const scheme = window.matchMedia('(prefers-color-scheme: dark)')
    scheme.addEventListener('change', draw)
    return () => {
      observer.disconnect()
      scheme.removeEventListener('change', draw)
    }
  }, [data, symbols])

  return <canvas ref={ref} className="roll-canvas" aria-hidden="true" />
}

function FormBar({ data, symbols }) {
  if (!data) return null
  return (
    <div className="form-bar" aria-hidden="true">
      {data.sections.map((s, i) => (
        <span
          key={i}
          className="form-cell"
          title={`${symbols[s.symbol] ?? s.symbol} · ${clock(s.start)}–${clock(s.end)}`}
          style={{
            width: `${((s.end - s.start) / data.duration) * 100}%`,
            background: `hsla(${hueFor(symbols, s.symbol)}, 55%, 50%, 0.28)`,
            borderColor: `hsla(${hueFor(symbols, s.symbol)}, 55%, 50%, 0.7)`,
          }}
        >
          {s.symbol}
        </span>
      ))}
    </div>
  )
}

function Track({ id, data, active, playing, loading, progress, onToggle, onSeek }) {
  const track = TRACKS[id]
  const seekFromPointer = (event) => {
    if (!data) return
    const box = event.currentTarget.getBoundingClientRect()
    onSeek(id, ((event.clientX - box.left) / box.width) * data.duration)
  }
  return (
    <li className={`track ${active ? 'track--active' : ''}`}>
      <div className="track-head">
        <button
          type="button"
          className="play"
          onClick={() => onToggle(id)}
          aria-label={`${active && playing ? 'Pause' : 'Play'} ${track.label}: ${track.title}`}
        >
          {active && loading ? <span className="spinner" /> : active && playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <div className="track-titles">
          <span className="chip">{track.label}</span>
          <h3>{track.title}</h3>
          <p className="summary">{track.summary}</p>
        </div>
        <span className="duration">{clock(data?.music_end ?? track.seconds)}</span>
      </div>

      <div
        className="roll"
        onClick={seekFromPointer}
        role="slider"
        tabIndex={0}
        aria-label={`Position in ${track.title}`}
        aria-valuemin={0}
        aria-valuemax={Math.round(data?.duration ?? track.seconds)}
        aria-valuenow={Math.round(active ? progress : 0)}
        aria-valuetext={clock(active ? progress : 0)}
        onKeyDown={(e) => {
          if (!data) return
          if (e.key === 'ArrowRight') onSeek(id, (active ? progress : 0) + 5)
          if (e.key === 'ArrowLeft') onSeek(id, (active ? progress : 0) - 5)
        }}
      >
        {data ? <PianoRoll data={data} symbols={track.symbols} /> : <div className="roll-placeholder" />}
        {active && data && (
          <span className="playhead" style={{ left: `${Math.min(100, (progress / data.duration) * 100)}%` }} />
        )}
      </div>
      <FormBar data={data} symbols={track.symbols} />

      <p className="description">{track.description}</p>
      <div className="track-foot">
        <ul className="legend">
          {Object.entries(track.symbols).map(([symbol, name]) => (
            <li key={symbol}>
              <i style={{ background: `hsla(${hueFor(track.symbols, symbol)}, 55%, 50%, 0.6)` }} />
              <b>{symbol}</b> {name}
            </li>
          ))}
        </ul>
        <span className="facts">
          {data ? `${data.n_notes.toLocaleString('en-GB')} notes` : ''}
          <a href={`${BASE}midi/${id}.mid`} download>
            MIDI
          </a>
        </span>
      </div>
    </li>
  )
}

const PlayIcon = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
    <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
  </svg>
)
const PauseIcon = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
    <path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor" />
  </svg>
)
const SkipIcon = ({ back }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" style={back ? { transform: 'scaleX(-1)' } : undefined}>
    <path d="M6 6l9 6-9 6zM16 6h2v12h-2z" fill="currentColor" />
  </svg>
)

export default function App() {
  const audioRef = useRef(null)
  const [data, setData] = useState({})
  const [current, setCurrent] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    ORDER.forEach((id) => {
      fetch(`${BASE}data/${id}.json`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
        .then((json) => alive && setData((d) => ({ ...d, [id]: json })))
        .catch(() => {})
    })
    return () => {
      alive = false
    }
  }, [])

  const start = useCallback((id, at = 0) => {
    const audio = audioRef.current
    setError(null)
    setCurrent(id)
    setLoading(true)
    audio.src = `${BASE}audio/${id}.mp3`
    audio.currentTime = 0
    const begin = () => {
      if (at > 0) audio.currentTime = at
      audio.play().catch(() => setLoading(false))
    }
    if (at > 0) audio.addEventListener('loadedmetadata', begin, { once: true })
    else begin()
  }, [])

  const toggle = useCallback(
    (id) => {
      const audio = audioRef.current
      if (id !== current) return start(id)
      if (audio.paused) audio.play().catch(() => {})
      else audio.pause()
      return undefined
    },
    [current, start],
  )

  const seek = useCallback(
    (id, seconds) => {
      const audio = audioRef.current
      const t = Math.max(0, seconds)
      if (id !== current) return start(id, t)
      audio.currentTime = Math.min(t, (audio.duration || t) - 0.05)
      if (audio.paused) audio.play().catch(() => {})
      return undefined
    },
    [current, start],
  )

  const step = useCallback(
    (delta) => {
      const i = ORDER.indexOf(current)
      const next = ORDER[i + delta]
      if (next) start(next)
    },
    [current, start],
  )

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest('button, a, input, [role="slider"]')) return
      if (e.code === 'Space') {
        e.preventDefault()
        toggle(current ?? ORDER[0])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [current, toggle])

  const now = current ? TRACKS[current] : null
  const total = current ? data[current]?.duration : 0
  const index = useMemo(() => ORDER.indexOf(current), [current])

  return (
    <div className="page">
      <header className="hero">
        <p className="eyebrow">Algorithmic composition for the Yamaha Disklavier</p>
        <h1>Amanous</h1>
        <p className="lede">
          Piano music at densities no pianist can reach. A grammar orders the sections, each section switches to its own
          family of probability distributions, tempo canons time the voices, and a hardware layer keeps every note
          within what the instrument&rsquo;s keys can physically do.
        </p>
        <nav className="links" aria-label="Project links">
          <a href={LINKS.code}>Code and data</a>
          <a href={LINKS.paper}>Journal of Creative Music Systems</a>
        </nav>
        <p className="note">
          The audio is a software render of the generated MIDI through a sampled piano, not a recording of a Disklavier.
        </p>
      </header>

      <main>
        {error && (
          <p className="error" role="alert">
            This track could not be loaded. Check your connection and try again.
          </p>
        )}
        {GROUPS.map((group) => (
          <section key={group.id} className="group" aria-labelledby={`group-${group.id}`}>
            <h2 id={`group-${group.id}`}>{group.title}</h2>
            <p className="group-blurb">{group.blurb}</p>
            <ul className="tracks">
              {group.tracks.map((id) => (
                <Track
                  key={id}
                  id={id}
                  data={data[id]}
                  active={current === id}
                  playing={playing}
                  loading={loading}
                  progress={progress}
                  onToggle={toggle}
                  onSeek={seek}
                />
              ))}
            </ul>
          </section>
        ))}
        <p className="hint">
          Click anywhere on a piano roll to start from that point. Space plays and pauses. Each roll shows every note of
          the piece, with pitch on the vertical axis, loudness as opacity, and the sections of the form shaded beneath.
        </p>
      </main>

      <footer className="foot">
        <p>
          Joonhyung Bae, Culture Technology Research Institute, KAIST. &ldquo;Amanous: Distribution-Switching for
          Superhuman Piano Density on Disklavier&rdquo;, <i>Journal of Creative Music Systems</i>.
        </p>
      </footer>

      <div className={`bar ${current ? 'bar--open' : ''}`} role="region" aria-label="Player">
        <div className="bar-inner">
          <div className="bar-buttons">
            <button type="button" onClick={() => step(-1)} disabled={index <= 0} aria-label="Previous track">
              <SkipIcon back />
            </button>
            <button type="button" className="bar-play" onClick={() => toggle(current)} aria-label={playing ? 'Pause' : 'Play'}>
              {loading ? <span className="spinner" /> : playing ? <PauseIcon /> : <PlayIcon />}
            </button>
            <button type="button" onClick={() => step(1)} disabled={index < 0 || index >= ORDER.length - 1} aria-label="Next track">
              <SkipIcon />
            </button>
          </div>
          <div className="bar-now">
            <span className="bar-title">{now ? `${now.label} · ${now.title}` : ''}</span>
            <div className="bar-seek">
              <span>{clock(progress)}</span>
              <input
                type="range"
                min={0}
                max={total || 1}
                step={0.1}
                value={Math.min(progress, total || 1)}
                onChange={(e) => seek(current, Number(e.target.value))}
                aria-label="Seek"
                style={{ '--fill': `${total ? (progress / total) * 100 : 0}%` }}
              />
              <span>{clock(total)}</span>
            </div>
          </div>
        </div>
      </div>

      <audio
        ref={audioRef}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onWaiting={() => setLoading(true)}
        onPlaying={() => setLoading(false)}
        onCanPlay={() => setLoading(false)}
        onTimeUpdate={(e) => setProgress(e.currentTarget.currentTime)}
        onEnded={() => {
          setPlaying(false)
          const next = ORDER[ORDER.indexOf(current) + 1]
          if (next) start(next)
        }}
        onError={() => {
          setLoading(false)
          setPlaying(false)
          setError(current)
        }}
      />
    </div>
  )
}
