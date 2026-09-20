import { useCallback, useEffect, useRef, useState } from 'react'
import { BIBTEX, GROUPS, LAYERS, LINKS, TRACKS } from './data/tracks'
import './App.css'

const BASE = import.meta.env.BASE_URL
const ORDER = GROUPS.flatMap((g) => g.tracks)
const SECTION_HUES = [38, 205, 150, 330, 270, 15]
// Okabe-Ito based, one colour per voice; readable on both schemes
const VOICE_LIGHT = ['#1f5fbf', '#c2410c', '#0f7b5f', '#7a3e9d', '#5b5b5b', '#8a6d12']
const VOICE_DARK = ['#7fb2ff', '#ff9d6b', '#5fd6b3', '#c89bf0', '#b5b5b5', '#e6c453']

const slug = (id) => TRACKS[id].label.toLowerCase().replace(/\s+/g, '-')

function clock(s) {
  if (!Number.isFinite(s)) return '0:00'
  const t = Math.max(0, Math.floor(s))
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}

function hueFor(symbols, symbol) {
  const i = Math.max(0, Object.keys(symbols).indexOf(symbol))
  return SECTION_HUES[i % SECTION_HUES.length]
}

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const keyName = (k) => `${NOTE_NAMES[k % 12]}${Math.floor(k / 12) - 1}`

function useDarkScheme() {
  const [dark, setDark] = useState(() => window.matchMedia('(prefers-color-scheme: dark)').matches)
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setDark(query.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return dark
}

/** Static piano roll. Playhead, played shade and hover line are DOM elements on top, so playback never redraws it. */
function PianoRoll({ data, symbols, dark }) {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !data) return undefined
    const draw = () => {
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (!w || !h) return
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      const ctx = canvas.getContext('2d')
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, w, h)
      const palette = dark ? VOICE_DARK : VOICE_LIGHT
      const span = data.music_end
      const lo = data.key_range[0] - 1
      const hi = data.key_range[1] + 1
      const range = Math.max(12, hi - lo)
      const y = (key) => h - ((key - lo) / range) * h
      const noteH = Math.max(1.5, Math.min(5, h / range))

      for (const s of data.sections) {
        ctx.fillStyle = `hsla(${hueFor(symbols, s.symbol)}, 60%, 50%, ${dark ? 0.17 : 0.1})`
        ctx.fillRect((s.start / span) * w, 0, ((s.end - s.start) / span) * w, h)
      }

      const faint = dark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.08)'
      const label = dark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)'
      ctx.font = '10px "DM Sans Variable", system-ui, sans-serif'
      ctx.textBaseline = 'middle'
      for (let c = 12 * Math.ceil(lo / 12); c <= hi; c += 12) {
        ctx.fillStyle = faint
        ctx.fillRect(0, Math.round(y(c)), w, 1)
      }
      const tick = span > 60 ? 10 : 5
      for (let t = tick; t < span - 1; t += tick) {
        ctx.fillStyle = faint
        ctx.fillRect(Math.round((t / span) * w), 0, 1, h)
      }

      for (const [t, key, vel, dur, voice] of data.notes) {
        ctx.globalAlpha = 0.35 + 0.65 * (vel / 127)
        ctx.fillStyle = palette[voice % palette.length]
        ctx.fillRect((t / span) * w, y(key) - noteH / 2, Math.max(1.4, (dur / span) * w), noteH)
      }
      ctx.globalAlpha = 1

      // axis labels go on last, on a backing, so that dense passages cannot hide them
      const backing = dark ? 'rgba(18,18,17,0.78)' : 'rgba(251,250,246,0.82)'
      const tag = (text, x, yy) => {
        const tw = ctx.measureText(text).width
        ctx.fillStyle = backing
        ctx.fillRect(x - 2, yy - 11, tw + 4, 12)
        ctx.fillStyle = label
        ctx.fillText(text, x, yy)
      }
      ctx.textBaseline = 'bottom'
      const octaveStep = (h / range) * 12 < 20 ? 24 : 12      // thin the labels out on short rolls
      for (let c = 12 * Math.ceil(lo / 12); c <= hi; c += octaveStep) tag(keyName(c), 4, Math.min(h - 14, Math.max(12, y(c) - 1)))
      for (let t = tick; t < span - 1; t += tick) tag(clock(t), Math.round((t / span) * w) + 3, h - 2)
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    document.fonts?.ready.then(draw)
    return () => observer.disconnect()
  }, [data, symbols, dark])

  return <canvas ref={ref} className="roll-canvas" aria-hidden="true" />
}

function Roll({ id, data, active, progress, onSeek, dark }) {
  const track = TRACKS[id]
  const [hover, setHover] = useState(null)
  const span = data?.music_end ?? track.seconds
  const at = active ? Math.min(progress, span) : 0

  const fraction = (event) => {
    const box = event.currentTarget.getBoundingClientRect()
    return Math.min(1, Math.max(0, (event.clientX - box.left) / box.width))
  }
  const onKey = (e) => {
    const jump = { ArrowRight: at + 5, ArrowLeft: at - 5, PageUp: at + 15, PageDown: at - 15, Home: 0, End: span - 1 }[e.key]
    if (jump === undefined) return
    e.preventDefault()
    onSeek(id, Math.min(span - 0.5, Math.max(0, jump)))
  }

  return (
    <div className="roll-wrap">
      <div
        className="roll"
        role="slider"
        tabIndex={0}
        aria-label={`Position in ${track.title}. ${track.summary}`}
        aria-valuemin={0}
        aria-valuemax={Math.round(span)}
        aria-valuenow={Math.round(at)}
        aria-valuetext={`${clock(at)} of ${clock(span)}`}
        onClick={(e) => onSeek(id, fraction(e) * span)}
        onMouseMove={(e) => setHover(fraction(e))}
        onMouseLeave={() => setHover(null)}
        onKeyDown={onKey}
      >
        {data ? <PianoRoll data={data} symbols={track.symbols} dark={dark} /> : <div className="roll-placeholder" />}
        {active && <span className="played" style={{ width: `${(at / span) * 100}%` }} />}
        {active && <span className="playhead" style={{ left: `${(at / span) * 100}%` }} />}
        {hover !== null && (
          <span className="hover-line" style={{ left: `${hover * 100}%` }}>
            <em className={hover > 0.8 ? 'flip' : ''}>{clock(hover * span)} · play from here</em>
          </span>
        )}
      </div>
      {data && (
        <div className="form-bar" aria-hidden="true">
          {data.sections.map((s, i) => (
            <span
              key={i}
              className="form-cell"
              title={`${track.symbols[s.symbol] ?? s.symbol} · ${clock(s.start)}–${clock(s.end)}`}
              style={{
                width: `${((s.end - s.start) / span) * 100}%`,
                background: `hsla(${hueFor(track.symbols, s.symbol)}, 55%, 50%, 0.3)`,
                borderColor: `hsla(${hueFor(track.symbols, s.symbol)}, 55%, 45%, 0.75)`,
              }}
            >
              {s.symbol}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function Track({ id, data, active, playing, loading, progress, onToggle, onSeek, dark }) {
  const track = TRACKS[id]
  const palette = dark ? VOICE_DARK : VOICE_LIGHT
  return (
    <li id={slug(id)} className={`track ${active ? 'track--active' : ''}`}>
      <div className="track-info">
        <div className="track-head">
          <button
            type="button"
            className={`play ${active && playing ? 'play--on' : ''}`}
            onClick={() => onToggle(id)}
            aria-label={`${active && playing ? 'Pause' : 'Play'} ${track.label}: ${track.title}`}
          >
            {active && loading ? <span className="spinner" /> : active && playing ? <PauseIcon /> : <PlayIcon />}
          </button>
          <div className="track-titles">
            <a className="chip" href={`#${slug(id)}`}>
              {track.label}
            </a>
            <h3>{track.title}</h3>
          </div>
        </div>
        <p className="summary">{track.summary}</p>
        <p className="description">{track.description}</p>
        <ul className="legend" aria-label="Sections">
          {Object.entries(track.symbols).map(([symbol, name]) => (
            <li key={symbol}>
              <i style={{ background: `hsla(${hueFor(track.symbols, symbol)}, 55%, 50%, 0.55)` }} />
              <b>{symbol}</b> {name}
            </li>
          ))}
        </ul>
        {data && (
          <ul className="legend legend--voices" aria-label="Voices">
            {data.voices.map((name, i) => (
              <li key={name}>
                <i className="dot" style={{ background: palette[i % palette.length] }} />
                {name}
              </li>
            ))}
          </ul>
        )}
        <p className="facts">
          <span>{clock(data?.music_end ?? track.seconds)}</span>
          {data && <span>{data.n_notes.toLocaleString('en-GB')} notes</span>}
          <a href={`${BASE}midi/${id}.mid`} download>
            Download MIDI
          </a>
        </p>
      </div>
      <Roll id={id} data={data} active={active} progress={progress} onSeek={onSeek} dark={dark} />
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
const VolumeIcon = ({ muted }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path d="M4 9v6h4l5 4V5L8 9z" fill="currentColor" />
    {muted ? (
      <path d="M16 9l5 6m0-6l-5 6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
    ) : (
      <path d="M16 8.5a5 5 0 010 7M18.5 6a8.5 8.5 0 010 12" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
    )}
  </svg>
)

export default function App() {
  const audioRef = useRef(null)
  const dark = useDarkScheme()
  const [data, setData] = useState({})
  const [current, setCurrent] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [volume, setVolume] = useState(0.8)
  const [muted, setMuted] = useState(false)
  const [error, setError] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let alive = true
    Promise.all(
      ORDER.map((id) =>
        fetch(`${BASE}data/${id}.json`)
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
          .then((json) => alive && setData((d) => ({ ...d, [id]: json })))
          .catch(() => {}),
      ),
    ).then(() => {
      // the cards are rendered by script, so a link to #excerpt-3 has to be honoured by hand
      const target = window.location.hash && document.getElementById(window.location.hash.slice(1))
      if (alive && target) target.scrollIntoView()
    })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    audio.volume = volume
    audio.muted = muted
  }, [volume, muted])

  const start = useCallback((id, at = 0) => {
    const audio = audioRef.current
    setError(false)
    setCurrent(id)
    setProgress(at)
    setLoading(true)
    audio.src = `${BASE}audio/${id}.mp3`
    // play() is called straight away so that it stays inside the user's click. With
    // preload="none" nothing loads until then, so a start position is applied once the
    // metadata arrives.
    if (at > 0) {
      audio.addEventListener('loadedmetadata', () => { audio.currentTime = at }, { once: true })
    }
    audio.play().catch(() => setLoading(false))
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
      audio.currentTime = Math.min(t, (audio.duration || t + 1) - 0.05)
      if (audio.paused) audio.play().catch(() => {})
      return undefined
    },
    [current, start],
  )

  const reveal = (id) => document.getElementById(slug(id))?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  const step = useCallback(
    (delta) => {
      const next = ORDER[ORDER.indexOf(current) + delta]
      if (next) {
        start(next)
        reveal(next)
      }
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

  const copyBibtex = async () => {
    try {
      await navigator.clipboard.writeText(BIBTEX)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const now = current ? TRACKS[current] : null
  const total = current ? data[current]?.music_end ?? now.seconds : 0
  const shown = Math.min(progress, total)
  const index = ORDER.indexOf(current)

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">Algorithmic composition for the Yamaha Disklavier</p>
          <h1>Amanous</h1>
          <p className="lede">
            Piano music at densities no pianist can reach, composed by rule. Every note below is drawn as it was
            generated, and every piece can be played from any point.
          </p>
          <div className="actions">
            <button
              type="button"
              className="button button--primary"
              onClick={() => {
                reveal(ORDER[0])
                if (!current) start(ORDER[0])
              }}
            >
              <PlayIcon /> Listen
            </button>
            <a className="button" href={LINKS.code}>
              Code and data
            </a>
            <a className="button" href={LINKS.paper}>
              Journal site
            </a>
          </div>
          <p className="note">
            The audio is a software render of the generated MIDI through a sampled piano, not a recording of a
            Disklavier.
          </p>
        </div>
        <ol className="layers" aria-label="The four layers of the system">
          {LAYERS.map((layer, i) => (
            <li key={layer.name}>
              <span className="layer-index">{i + 1}</span>
              <span>
                <b>{layer.name}</b>
                {layer.text}
              </span>
            </li>
          ))}
        </ol>
      </header>

      <nav className="index" aria-label="All pieces">
        {GROUPS.map((group) => (
          <div key={group.id} className={`index-group index-group--${group.id}`}>
            <span className="index-title">{group.title}</span>
            <ul>
              {group.tracks.map((id) => (
                <li key={id}>
                  <button
                    type="button"
                    className={`index-item ${current === id ? 'index-item--on' : ''}`}
                    onClick={() => {
                      reveal(id)
                      if (current !== id) start(id)
                    }}
                  >
                    <span className="index-label">{TRACKS[id].label}</span>
                    <span className="index-name">{TRACKS[id].title}</span>
                    <span className="index-time">{clock(data[id]?.music_end ?? TRACKS[id].seconds)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <main>
        {error && (
          <p className="error" role="alert">
            This track could not be loaded. Check your connection and try again.
          </p>
        )}
        {GROUPS.map((group) => (
          <section key={group.id} className={`group group--${group.id}`} aria-labelledby={`group-${group.id}`}>
            <div className="group-head">
              <h2 id={`group-${group.id}`}>{group.title}</h2>
              {group.badge && <span className="badge">{group.badge}</span>}
            </div>
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
                  dark={dark}
                />
              ))}
            </ul>
          </section>
        ))}
      </main>

      <footer className="foot">
        <p>
          Joonhyung Bae, Culture Technology Research Institute, KAIST. &ldquo;Amanous: Distribution-Switching for
          Superhuman Piano Density on Disklavier&rdquo;, <i>Journal of Creative Music Systems</i>, in press.
        </p>
        <button type="button" className="button button--small" onClick={copyBibtex}>
          {copied ? 'Copied' : 'Copy BibTeX'}
        </button>
      </footer>

      <div className={`bar ${current ? 'bar--open' : ''}`} role="region" aria-label="Player">
        <div className="bar-inner">
          <div className="bar-buttons">
            <button type="button" onClick={() => step(-1)} onMouseUp={(e) => e.currentTarget.blur()} disabled={index <= 0} aria-label="Previous piece">
              <SkipIcon back />
            </button>
            <button type="button" className="bar-play" onClick={() => toggle(current)} aria-label={playing ? 'Pause' : 'Play'}>
              {loading ? <span className="spinner" /> : playing ? <PauseIcon /> : <PlayIcon />}
            </button>
            <button type="button" onClick={() => step(1)} onMouseUp={(e) => e.currentTarget.blur()} disabled={index < 0 || index >= ORDER.length - 1} aria-label="Next piece">
              <SkipIcon />
            </button>
          </div>
          <div className="bar-now">
            <span className="bar-title">{now ? `${now.label} · ${now.title}` : ''}</span>
            <div className="bar-seek">
              <span>{clock(shown)}</span>
              <input
                type="range"
                min={0}
                max={total || 1}
                step={0.1}
                value={shown}
                onChange={(e) => seek(current, Number(e.target.value))}
                aria-label="Seek"
                style={{ '--fill': `${total ? (shown / total) * 100 : 0}%` }}
              />
              <span>{clock(total)}</span>
            </div>
          </div>
          <div className="bar-volume">
            <button type="button" onClick={() => setMuted((m) => !m)} onMouseUp={(e) => e.currentTarget.blur()} aria-label={muted ? 'Unmute' : 'Mute'}>
              <VolumeIcon muted={muted || volume === 0} />
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={muted ? 0 : volume}
              onChange={(e) => {
                setVolume(Number(e.target.value))
                setMuted(false)
              }}
              aria-label="Volume"
              style={{ '--fill': `${(muted ? 0 : volume) * 100}%` }}
            />
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
          setError(true)
        }}
      />
    </div>
  )
}
