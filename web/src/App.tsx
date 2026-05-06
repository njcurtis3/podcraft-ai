import { useState } from 'react'
import EpisodeList from './components/EpisodeList'
import RunPipeline from './components/RunPipeline'

export default function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <h1 className="app-title">🎙 PodCraft AI</h1>
          <p className="app-subtitle">AI-generated podcast episodes, end to end</p>
        </div>
      </header>

      <main className="app-main">
        <section className="panel panel--left">
          <h2 className="panel-heading">Episodes</h2>
          <EpisodeList refreshTrigger={refreshTrigger} />
        </section>

        <section className="panel panel--right">
          <h2 className="panel-heading">Generate Episode</h2>
          <RunPipeline onRunComplete={() => setRefreshTrigger((n) => n + 1)} />
        </section>
      </main>
    </div>
  )
}
