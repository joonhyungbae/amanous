import { useRef, useState, useCallback } from 'react'
import { TRACK_ORDER, TRACKS } from './data/tracks'
import './App.css'

function getAudioUrl(trackId) {
  const base = import.meta.env.BASE_URL
  return `${base}audio/${trackId}.wav`
}

function App() {
  const audioRef = useRef(null)
  const [currentTrackId, setCurrentTrackId] = useState(null)
  const [audioError, setAudioError] = useState(null)
  // descriptions expanded by default; track ids in this set are collapsed
  const [collapsedIds, setCollapsedIds] = useState(() => new Set())

  const handlePlay = useCallback((trackId) => {
    setAudioError(null)
    const audio = audioRef.current
    if (!audio) return
    const url = getAudioUrl(trackId)
    if (audio.src && audio.src === new URL(url, window.location.origin).href && !audio.paused) {
      audio.pause()
      setCurrentTrackId(null)
      return
    }
    audio.src = url
    audio.load()
    audio.play().catch(() => {
      setAudioError(trackId)
    })
    setCurrentTrackId(trackId)
  }, [])

  const handleAudioError = useCallback(() => {
    if (currentTrackId) setAudioError(currentTrackId)
  }, [currentTrackId])

  const handleAudioEnded = useCallback(() => {
    setCurrentTrackId(null)
  }, [])

  return (
    <div className="app">
      <header className="header">
        <h1>AMANOUS</h1>
        <p className="subtitle">Piano pieces only a Disklavier can play — composed by algorithm.</p>
        <p className="subtitle">Audio is a software render of the generated MIDI (piano soundfont), not a recording of the instrument.</p>
      </header>

      {audioError && (
        <div className="error-banner" role="alert">
          Could not load audio. Add WAV files to <code>web/public/audio/</code> and rebuild.
        </div>
      )}

      <div className="player-wrap">
        <audio
          ref={audioRef}
          controls
          onError={handleAudioError}
          onEnded={handleAudioEnded}
          className="global-audio"
        />
      </div>

      <ul className="track-list">
        {TRACK_ORDER.map((id) => {
          const track = TRACKS[id]
          const isExpanded = !collapsedIds.has(id)
          const isPlaying = currentTrackId === id
          const hasError = audioError === id
          return (
            <li key={id} className={`track-item ${hasError ? 'track-item--error' : ''} ${isPlaying ? 'track-item--playing' : ''}`}>
              <div className="track-header">
                <div className="track-meta">
                  <span className="track-title">{track.title}</span>
                  <span className="track-style">{track.style}</span>
                  <span className="track-duration">{track.duration}</span>
                </div>
                <button
                  type="button"
                  className="track-play"
                  onClick={() => handlePlay(id)}
                  disabled={hasError}
                  aria-pressed={isPlaying}
                >
                  {isPlaying ? 'Pause' : 'Play'}
                </button>
              </div>
              {hasError && (
                <p className="track-error-msg">Audio file for this track is not available.</p>
              )}
              <button
                type="button"
                className="track-toggle-desc"
                onClick={() => setCollapsedIds((prev) => {
                  const next = new Set(prev)
                  if (next.has(id)) next.delete(id)
                  else next.add(id)
                  return next
                })}
                aria-expanded={isExpanded}
              >
                {isExpanded ? 'Hide description' : 'Show description'}
              </button>
              {isExpanded && (
                <div className="track-detail">
                  <p>{track.description}</p>
                  <p className="track-highlight">{track.highlight}</p>
                </div>
              )}
            </li>
          )
        })}
      </ul>

    </div>
  )
}

export default App
