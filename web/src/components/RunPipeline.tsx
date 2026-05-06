import { useEffect, useRef, useState } from 'react'
import type { RunStatus } from '../types'
import { startRun, openLogStream } from '../api'

interface Props {
  onRunComplete: () => void
}

export default function RunPipeline({ onRunComplete }: Props) {
  const [topic, setTopic] = useState('')
  const [episodeNum, setEpisodeNum] = useState(1)
  const [devMode, setDevMode] = useState(true)
  const [status, setStatus] = useState<RunStatus>('idle')
  const [logs, setLogs] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    return () => esRef.current?.close()
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim()) return

    setLogs([])
    setError(null)
    setStatus('pending')

    let runId: string
    try {
      runId = await startRun(topic.trim(), episodeNum, devMode)
    } catch (err) {
      setError(String(err))
      setStatus('error')
      return
    }

    setStatus('running')
    const es = openLogStream(runId)
    esRef.current = es

    es.onmessage = (event) => {
      const data: string = event.data
      if (data.startsWith('__STATUS__')) {
        const finalStatus = data.replace('__STATUS__', '') as RunStatus
        setStatus(finalStatus)
        es.close()
        if (finalStatus === 'done') onRunComplete()
      } else {
        setLogs((prev) => [...prev, data])
      }
    }

    es.onerror = () => {
      setStatus('error')
      setError('Lost connection to server.')
      es.close()
    }
  }

  const isRunning = status === 'pending' || status === 'running'

  return (
    <div className="run-pipeline">
      <form onSubmit={handleSubmit} className="run-form">
        <div className="field">
          <label htmlFor="topic">Topic</label>
          <input
            id="topic"
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. The impact of AI on newsroom employment"
            disabled={isRunning}
            required
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="episode-num">Episode #</label>
            <input
              id="episode-num"
              type="number"
              min={1}
              value={episodeNum}
              onChange={(e) => setEpisodeNum(Number(e.target.value))}
              disabled={isRunning}
            />
          </div>

          <div className="field field-checkbox">
            <label htmlFor="dev-mode">
              <input
                id="dev-mode"
                type="checkbox"
                checked={devMode}
                onChange={(e) => setDevMode(e.target.checked)}
                disabled={isRunning}
              />
              Dev mode (2 TTS turns only)
            </label>
          </div>
        </div>

        <button type="submit" className="run-btn" disabled={isRunning || !topic.trim()}>
          {isRunning ? 'Running…' : 'Generate Episode'}
        </button>
      </form>

      {status !== 'idle' && (
        <div className="log-console">
          <div className="log-console-header">
            <span>Pipeline log</span>
            <span className={`run-badge run-badge--${status}`}>{status}</span>
          </div>
          <div className="log-body">
            {logs.map((line, i) => (
              <div key={i} className="log-line">{line}</div>
            ))}
            {isRunning && <div className="log-line log-line--cursor">▋</div>}
            <div ref={logEndRef} />
          </div>
          {error && <p className="log-error">{error}</p>}
        </div>
      )}
    </div>
  )
}
