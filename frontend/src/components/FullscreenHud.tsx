import { useEffect, useState } from 'react'
import { energyWord, num, toneVar } from '../lib/format'
import type { EngineStatus, LabelMeta, Point, Snapshot } from '../lib/types'

const SPARK_S = 5 * 60
const SPARK_W = 300
const SPARK_H = 130

/**
 * Tam ekran (sunum) modunda görüntünün yanında duran canlı veri paneli.
 * Projeksiyonda birkaç metreden okunabilsin diye büyük, az ve net.
 */
export function FullscreenHud({
  snapshot,
  series,
  labels,
  status,
}: {
  snapshot: Snapshot | null
  series: Point[]
  labels: LabelMeta[]
  status: EngineStatus | null
}) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const a = snapshot?.atmosphere
  const tone = a?.tone ?? 'unknown'
  const label = (key: string) => labels.find((l) => l.key === key)?.label ?? key
  const top = snapshot?.emotions
    ? Object.entries(snapshot.emotions)
        .sort((x, y) => y[1] - x[1])
        .slice(0, 4)
    : []

  return (
    <aside
      aria-label="Canlı özet"
      className="flex h-full w-[380px] shrink-0 flex-col gap-8 overflow-y-auto border-l border-line bg-board px-8 py-7 text-chalk"
    >
      <header className="flex items-center justify-between">
        <p className="display text-xl font-bold">VibeSight</p>
        <p className="numeric text-2xl text-chalk-2">
          {now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
        </p>
      </header>

      <section aria-live="polite">
        <h2 className="text-sm text-chalk-3">Ortamın havası</h2>
        <p className="display mt-1 text-5xl font-semibold leading-[1.05]" style={{ color: toneVar(tone) }}>
          {a?.label ?? 'Bekleniyor'}
        </p>
        <p className="mt-3 text-[15px] leading-relaxed text-chalk-2">{a?.description}</p>
      </section>

      <dl className="grid grid-cols-3">
        <Big label="Kişi" value={snapshot ? String(snapshot.count) : '—'} />
        <Big
          label="Enerji"
          value={num(snapshot?.energy)}
          note={energyWord(snapshot?.energy)}
          meter={snapshot?.energy}
          color="var(--series-energy)"
        />
        <Big
          label="Dikkat"
          value={snapshot?.attention == null ? '—' : `%${num(snapshot.attention * 100)}`}
          meter={snapshot?.attention == null ? null : snapshot.attention * 100}
          color="var(--series-attention)"
        />
      </dl>

      <section>
        <h2 className="mb-3 text-sm text-chalk-3">Baskın ifadeler</h2>
        {top.length ? (
          <ul className="flex flex-col gap-2.5">
            {top.map(([key, v], i) => (
              <li key={key} className="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-3">
                <span className={i === 0 ? 'font-semibold' : 'text-chalk-2'}>{label(key)}</span>
                <span className="h-2 rounded-full bg-sunken" aria-hidden>
                  <span
                    className="block h-full rounded-full transition-[width] duration-300"
                    style={{ width: `${Math.max(v * 100, 1)}%`, background: i === 0 ? 'var(--bar)' : 'var(--bar-muted)' }}
                  />
                </span>
                <span className={`numeric text-right ${i === 0 ? 'font-semibold' : 'text-chalk-3'}`}>%{num(v * 100)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-chalk-3">Yüz görününce burada belirir.</p>
        )}
      </section>

      <Spark series={series} />

      <footer className="mt-auto flex items-end justify-between gap-4 text-[13px] text-chalk-3">
        <span>
          {snapshot ? `${snapshot.faces_analyzed}/${snapshot.count} yüz analiz ediliyor` : ''}
          {status && status.analysis_fps > 0 && (
            <>
              <br />
              saniyede {num(status.analysis_fps, 0)} güncelleme
            </>
          )}
        </span>
        <span className="whitespace-nowrap">
          <kbd className="rounded border border-line-strong px-1.5 py-0.5 text-chalk-2">Esc</kbd> ile çık
        </span>
      </footer>
    </aside>
  )
}

function Big({
  label,
  value,
  note,
  meter,
  color,
}: {
  label: string
  value: string
  note?: string
  meter?: number | null
  color?: string
}) {
  return (
    <div className="border-l border-line pl-4 first:border-l-0 first:pl-0">
      <dt className="text-sm text-chalk-3">{label}</dt>
      <dd className="numeric mt-1 text-4xl font-semibold leading-none">{value}</dd>
      {meter !== undefined && (
        <dd className="mt-3 h-1 w-full max-w-20 overflow-hidden rounded-full bg-line" aria-hidden>
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${Math.max(0, Math.min(100, meter ?? 0))}%`, background: color }}
          />
        </dd>
      )}
      {note && <dd className="mt-2 text-[13px] text-chalk-3">{note}</dd>}
    </div>
  )
}

function Spark({ series }: { series: Point[] }) {
  const end = series.at(-1)?.t
  if (end == null) return null
  const t0 = end - SPARK_S
  const pts = series.filter((p) => p.t >= t0)
  const x = (t: number) => ((t - t0) / SPARK_S) * SPARK_W
  const y = (v: number) => 4 + (1 - v / 100) * (SPARK_H - 8)
  const path = (key: 'energy' | 'attention') => {
    let d = ''
    let prev: Point | null = null
    for (const p of pts) {
      const v = p[key]
      if (v == null) {
        prev = null
        continue
      }
      d += `${prev && p.t - prev.t <= 12 ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(v).toFixed(1)}`
      prev = p
    }
    return d
  }
  return (
    <section>
      <div className="mb-2 flex items-center justify-between text-sm text-chalk-3">
        <h2>Son 5 dakika</h2>
        <ul className="flex gap-4" aria-label="Seriler">
          <li className="flex items-center gap-1.5">
            <span className="h-0.5 w-3.5 rounded-full bg-[var(--series-energy)]" aria-hidden />
            Enerji
          </li>
          <li className="flex items-center gap-1.5">
            <span className="h-0.5 w-3.5 rounded-full bg-[var(--series-attention)]" aria-hidden />
            Dikkat
          </li>
        </ul>
      </div>
      <svg
        viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
        className="block w-full"
        role="img"
        aria-label="Son 5 dakikada enerji ve dikkat"
      >
        {[0, 50, 100].map((v) => (
          <line key={v} x1={0} x2={SPARK_W} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth={1} />
        ))}
        <path d={path('attention')} fill="none" stroke="var(--series-attention)" strokeWidth={2} strokeLinejoin="round" />
        <path d={path('energy')} fill="none" stroke="var(--series-energy)" strokeWidth={2} strokeLinejoin="round" />
      </svg>
    </section>
  )
}
