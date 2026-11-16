export type Tone = 'positive' | 'focused' | 'calm' | 'tired' | 'tense' | 'unknown'

export interface Atmosphere {
  key: string
  label: string
  tone: Tone
  description: string
}

export interface Person {
  id: number
  box: [number, number, number, number]
  face?: [number, number, number, number]
  emotion?: string
  emotion_label?: string
  confidence?: number
  energy?: number | null
  attentive?: boolean | null
}

export interface Snapshot {
  t: number
  count: number
  raw_count: number
  peak_count: number
  faces_analyzed: number
  emotions: Record<string, number> | null
  dominant_emotion: string | null
  dominant_emotion_label: string | null
  valence: number | null
  arousal: number | null
  energy: number | null
  attention: number | null
  perclos: number | null
  activity: number | null
  yawns_recent: number
  atmosphere: Atmosphere
  people: Person[]
}

export interface SourceStatus {
  label: string
  kind: 'webcam' | 'stream' | 'file' | 'mock'
  status: 'connecting' | 'live' | 'reconnecting' | 'stopped'
  fps: number
  resolution: [number, number] | null
}

export interface EngineStatus {
  mode: 'live' | 'mock'
  source: SourceStatus
  analysis_fps: number
  stream_fps: number
  latency_ms: number
  privacy_blur: boolean
  uptime_s: number
  models: Record<string, { name: string; loaded: boolean }>
}

export interface LabelMeta {
  key: string
  label: string
  valence: number
  arousal: number
}

export interface Meta {
  version: string
  labels: LabelMeta[]
  analysis_hz: number
  history_interval_s: number
}

/** Zaman serisi noktası (canlı tampon ve /api/history ortak biçimi). */
export interface Point {
  t: number
  count: number
  energy: number | null
  attention: number | null
  valence: number | null
  arousal: number | null
  atmosphere: string | null
}
