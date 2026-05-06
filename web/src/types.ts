export interface Episode {
  title: string
  episode: number
  published: string
  duration_estimate: string
  description: string
  tags: string[]
  chapters: string[]
  mp3_path: string
  mp3_url: string | null
}

export type RunStatus = 'idle' | 'pending' | 'running' | 'done' | 'error'
