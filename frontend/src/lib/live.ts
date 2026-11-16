import { useCallback, useEffect, useRef, useState } from 'react'
import type { EngineStatus, Meta, Point, Snapshot } from './types'

export type Connection = 'connecting' | 'open' | 'closed'

const MAX_SERIES_S = 60 * 60
const SERIES_STEP_S = 1

function toPoint(s: {
  t: number
  count: number
  energy: number | null
  attention: number | null
  valence: number | null
  arousal: number | null
  atmosphere?: string | { key: string } | null
}): Point {
  return {
    t: s.t,
    count: s.count,
    energy: s.energy,
    attention: s.attention == null ? null : s.attention * 100,
    valence: s.valence,
    arousal: s.arousal,
    atmosphere: typeof s.atmosphere === 'object' && s.atmosphere ? s.atmosphere.key : (s.atmosphere ?? null),
  }
}

function wsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/live`
}

/**
 * Canlı WebSocket akışı. Her ikili mesaj: [uint32 JSON uzunluğu][JSON][JPEG?].
 * Görüntü ve metrikler aynı mesajda geldiği için kutular kareyle hizalıdır.
 */
export function useLive() {
  const [connection, setConnection] = useState<Connection>('connecting')
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [status, setStatus] = useState<EngineStatus | null>(null)
  const [frameUrl, setFrameUrl] = useState<string | null>(null)
  const [frameSize, setFrameSize] = useState<{ w: number; h: number } | null>(null)
  const [series, setSeries] = useState<Point[]>([])
  const [meta, setMeta] = useState<Meta | null>(null)
  const lastPoint = useRef(0)
  const lastUrl = useRef<string | null>(null)

  useEffect(() => {
    let ws: WebSocket | null = null
    let retry = 0
    let timer: number | undefined
    let disposed = false

    const loadHistory = async () => {
      try {
        const [hist, m] = await Promise.all([
          fetch('/api/history?minutes=60').then((r) => r.json()),
          fetch('/api/meta').then((r) => r.json()),
        ])
        if (disposed) return
        setMeta(m as Meta)
        const points = (hist as Parameters<typeof toPoint>[0][]).map(toPoint)
        setSeries((prev) => {
          const first = prev[0]?.t ?? Infinity
          return [...points.filter((p) => p.t < first), ...prev]
        })
      } catch {
        /* sunucu henüz hazır değil; WebSocket yeniden denemesi bunu da kapsar */
      }
    }

    const connect = () => {
      setConnection('connecting')
      ws = new WebSocket(wsUrl())
      ws.binaryType = 'arraybuffer'
      ws.onopen = () => {
        retry = 0
        setConnection('open')
        void loadHistory()
      }
      ws.onmessage = (ev) => {
        const buf = ev.data as ArrayBuffer
        const view = new DataView(buf)
        const n = view.getUint32(0)
        const msg = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)))
        if (msg.status) setStatus(msg.status as EngineStatus)
        if (msg.frame && buf.byteLength > 4 + n) {
          const url = URL.createObjectURL(new Blob([new Uint8Array(buf, 4 + n)], { type: 'image/jpeg' }))
          if (lastUrl.current) URL.revokeObjectURL(lastUrl.current)
          lastUrl.current = url
          setFrameUrl(url)
          setFrameSize({ w: msg.frame.w, h: msg.frame.h })
        }
        if (msg.snapshot) {
          const s = msg.snapshot as Snapshot
          setSnapshot(s)
          if (s.t - lastPoint.current >= SERIES_STEP_S) {
            lastPoint.current = s.t
            setSeries((prev) => {
              const next = [...prev, toPoint(s)]
              const cutoff = s.t - MAX_SERIES_S
              let i = 0
              while (i < next.length && next[i].t < cutoff) i++
              return i ? next.slice(i) : next
            })
          }
        }
      }
      ws.onclose = () => {
        if (disposed) return
        setConnection('closed')
        retry = Math.min(retry + 1, 6)
        timer = window.setTimeout(connect, 500 * 2 ** retry)
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      ws?.close()
      if (lastUrl.current) URL.revokeObjectURL(lastUrl.current)
    }
  }, [])

  const setPrivacy = useCallback(async (on: boolean) => {
    const r = await fetch('/api/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ privacy_blur: on }),
    })
    if (r.ok) setStatus((await r.json()) as EngineStatus)
  }, [])

  return { connection, snapshot, status, frameUrl, frameSize, series, meta, setPrivacy }
}

export function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (document.documentElement.dataset.theme as 'dark' | 'light') ?? 'dark',
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('vibesight-theme', theme)
    } catch {
      /* gizli sekme */
    }
  }, [theme])
  return { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) }
}
