import { useState } from 'react'
import { num } from '../lib/format'
import type { LabelMeta, Point, Snapshot } from '../lib/types'
import { useWidth } from '../lib/useSize'

/** İfade dağılımı: sabit sıra (titremesin), baskın ifade vurgulu. */
export function EmotionBars({ snapshot, labels }: { snapshot: Snapshot | null; labels: LabelMeta[] }) {
  const dist = snapshot?.emotions
  const dominant = snapshot?.dominant_emotion
  return (
    <section aria-labelledby="emo-title" className="flex flex-col gap-4">
      <div>
        <h2 id="emo-title" className="display text-xl font-semibold">
          Gözlenen ifadeler
        </h2>
        <p className="text-sm text-chalk-3">Analiz edilen yüzlerin ortalaması</p>
      </div>
      {!dist ? (
        <p className="rounded-lg bg-sunken px-4 py-6 text-sm text-chalk-3 ring-1 ring-line">
          Yüz analiz edildiğinde ifade dağılımı burada görünür. İfade modeli yüklü değilse sağ alttaki model durumuna bakın.
        </p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {labels.map((l) => {
            const v = dist[l.key] ?? 0
            const isDom = l.key === dominant
            return (
              <li key={l.key} className="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-3 text-sm" title={`${l.label}: %${num(v * 100, 1)}`}>
                <span className={isDom ? 'font-semibold text-chalk' : 'text-chalk-2'}>{l.label}</span>
                <span className="relative h-2.5 rounded-full bg-sunken" aria-hidden>
                  <span
                    className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ease-out"
                    style={{
                      width: `${Math.max(v * 100, 1)}%`,
                      background: isDom ? 'var(--bar)' : 'var(--bar-muted)',
                    }}
                  />
                </span>
                <span className={`numeric text-right ${isDom ? 'font-semibold text-chalk' : 'text-chalk-3'}`}>
                  %{num(v * 100)}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

const QUADRANTS = [
  { x: 0, y: 0, label: 'Gergin', anchor: 'start' },
  { x: 1, y: 0, label: 'Coşkulu', anchor: 'end' },
  { x: 0, y: 1, label: 'Durgun', anchor: 'start' },
  { x: 1, y: 1, label: 'Rahat', anchor: 'end' },
] as const

/** Russell duygu çemberi: yatay valans (olumsuz → olumlu), dikey uyarılmışlık (sakin → uyarılmış). */
export function AffectPlane({ snapshot, series, labels }: { snapshot: Snapshot | null; series: Point[]; labels: LabelMeta[] }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<string | null>(null)
  const size = Math.min(width, 340)
  const pad = 22
  const s = (v: number) => pad + ((v + 1) / 2) * (size - 2 * pad)
  const sy = (v: number) => pad + ((1 - v) / 2) * (size - 2 * pad)

  const trail = series
    .slice(-90)
    .filter((p) => p.valence != null && p.arousal != null)
    .map((p) => `${s(p.valence as number).toFixed(1)},${sy(p.arousal as number).toFixed(1)}`)
    .join(' ')

  const v = snapshot?.valence
  const a = snapshot?.arousal

  return (
    <section aria-labelledby="affect-title" className="flex flex-col gap-4">
      <div>
        <h2 id="affect-title" className="display text-xl font-semibold">
          Duygu düzlemi
        </h2>
        <p className="text-sm text-chalk-3">Yatayda olumlu–olumsuz, dikeyde sakin–uyarılmış</p>
      </div>
      <div ref={ref} className="relative">
        {size > 0 && (
          <svg
            width={size}
            height={size}
            role="img"
            aria-label={
              v == null || a == null
                ? 'Duygu düzlemi: henüz veri yok'
                : `Oda konumu: valans ${num(v, 2)}, uyarılmışlık ${num(a, 2)}`
            }
            className="block"
          >
            <rect x={pad} y={pad} width={size - 2 * pad} height={size - 2 * pad} rx={10} fill="var(--board-sunken)" />
            <line x1={s(0)} x2={s(0)} y1={pad} y2={size - pad} stroke="var(--line-strong)" />
            <line x1={pad} x2={size - pad} y1={sy(0)} y2={sy(0)} stroke="var(--line-strong)" />
            {QUADRANTS.map((q) => (
              <text
                key={q.label}
                x={q.x ? size - pad - 10 : pad + 10}
                y={q.y ? size - pad - 10 : pad + 20}
                textAnchor={q.anchor}
                className="fill-chalk-3 text-[12px]"
              >
                {q.label}
              </text>
            ))}
            {labels.map((l) => (
              <g
                key={l.key}
                onPointerEnter={() => setHover(l.key)}
                onPointerLeave={() => setHover(null)}
                className="cursor-default"
              >
                <circle cx={s(l.valence)} cy={sy(l.arousal)} r={12} fill="transparent" />
                <circle cx={s(l.valence)} cy={sy(l.arousal)} r={3} fill="var(--chalk-3)" opacity={hover === l.key ? 1 : 0.55} />
                {hover === l.key && (
                  <text x={s(l.valence)} y={sy(l.arousal) - 10} textAnchor="middle" className="fill-chalk text-[12px] font-semibold">
                    {l.label}
                  </text>
                )}
              </g>
            ))}
            {trail && (
              <polyline points={trail} fill="none" stroke="var(--highlight)" strokeOpacity={0.35} strokeWidth={2} strokeLinejoin="round" />
            )}
            {v != null && a != null && (
              <g style={{ transition: 'transform 400ms ease-out' }} transform={`translate(${s(v)},${sy(a)})`}>
                <circle r={14} fill="var(--highlight)" opacity={0.18} />
                <circle r={6} fill="var(--highlight)" stroke="var(--board)" strokeWidth={2} />
              </g>
            )}
          </svg>
        )}
        <p className="mt-2 text-[13px] text-chalk-3">Nokta odanın şu anki konumu, soluk iz son 90 saniye.</p>
      </div>
    </section>
  )
}
