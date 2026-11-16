import type { Tone } from './types'

export const pct = (v: number | null | undefined, digits = 0) =>
  v == null ? '—' : `%${(v * 100).toLocaleString('tr-TR', { maximumFractionDigits: digits })}`

export const num = (v: number | null | undefined, digits = 0) =>
  v == null ? '—' : v.toLocaleString('tr-TR', { maximumFractionDigits: digits, minimumFractionDigits: digits })

export const clock = (t: number) =>
  new Date(t * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export const shortClock = (t: number) =>
  new Date(t * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })

export function duration(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h ? `${h} sa ${m} dk` : m ? `${m} dk` : `${Math.floor(s)} sn`
}

export const toneVar = (tone: Tone) => `var(--tone-${tone})`

export function energyWord(e: number | null | undefined) {
  if (e == null) return 'Ölçülemiyor'
  if (e >= 65) return 'Yüksek'
  if (e >= 45) return 'Orta'
  if (e >= 30) return 'Düşük'
  return 'Çok düşük'
}
