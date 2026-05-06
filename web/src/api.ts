import type { Episode } from './types'

export async function fetchEpisodes(): Promise<Episode[]> {
  const res = await fetch('/api/episodes')
  if (!res.ok) throw new Error(`Failed to fetch episodes: ${res.status}`)
  return res.json()
}

export async function startRun(
  topic: string,
  episodeNum: number,
  devMode: boolean,
): Promise<string> {
  const res = await fetch('/api/pipeline/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, episode_num: episodeNum, dev_mode: devMode }),
  })
  if (!res.ok) throw new Error(`Failed to start run: ${res.status}`)
  const data = await res.json()
  return data.run_id as string
}

export function openLogStream(runId: string): EventSource {
  return new EventSource(`/api/pipeline/run/${runId}/stream`)
}
