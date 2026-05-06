import { useEffect, useRef, useState } from 'react'
import type { Episode } from '../types'
import { fetchEpisodes } from '../api'

interface Props {
  refreshTrigger: number
}

export default function EpisodeList({ refreshTrigger }: Props) {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchEpisodes()
      .then(setEpisodes)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [refreshTrigger])

  function togglePlay(ep: Episode, idx: number) {
    if (!ep.mp3_url) return

    if (playing === idx) {
      audioRef.current?.pause()
      setPlaying(null)
      return
    }

    if (audioRef.current) {
      audioRef.current.pause()
    }

    const audio = new Audio(ep.mp3_url)
    audio.addEventListener('ended', () => setPlaying(null))
    audio.play()
    audioRef.current = audio
    setPlaying(idx)
  }

  if (loading) return <p className="status-text">Loading episodes…</p>
  if (error) return <p className="status-text error">Error: {error}</p>
  if (episodes.length === 0)
    return <p className="status-text muted">No episodes yet. Run the pipeline to generate one.</p>

  return (
    <ul className="episode-list">
      {episodes.map((ep, idx) => (
        <li key={ep.episode} className="episode-card">
          <div className="episode-header">
            <div className="episode-meta">
              <span className="episode-number">EP {ep.episode}</span>
              <span className="episode-duration">{ep.duration_estimate}</span>
            </div>
            {ep.mp3_url && (
              <button
                className={`play-btn ${playing === idx ? 'playing' : ''}`}
                onClick={() => togglePlay(ep, idx)}
                aria-label={playing === idx ? 'Pause' : 'Play'}
              >
                {playing === idx ? '⏸' : '▶'}
              </button>
            )}
          </div>

          <h3 className="episode-title">{ep.title}</h3>
          <p className="episode-description">{ep.description}</p>

          <div className="episode-tags">
            {ep.tags.map((tag) => (
              <span key={tag} className="tag">{tag}</span>
            ))}
          </div>

          <p className="episode-date">
            {new Date(ep.published).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })}
          </p>
        </li>
      ))}
    </ul>
  )
}
