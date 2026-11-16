import clsx from 'clsx'
import { Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { clock, num, shortClock } from '../lib/format'
import type { Point } from '../lib/types'
import { useWidth } from '../lib/useSize'

const RANGES = [
  { s: 5 * 60, label: '5 dk' },
  { s: 15 * 60, label: '15 dk' },
  { s: 60 * 60, label: '1 sa' },
]

const SERIES = [
  { key: 'energy', label: 'Enerji', color: 'var(--series-energy)' },
  { key: 'engagement', label: 'Katılım', color: 'var(--series-attention)' },
] as const

const H = 220
const M = { top: 12, right: 92, bottom: 26, left: 32 }
const GAP_S = 12 // bu süreden uzun boşlukta çizgi kesilir

export function PulseChart({ series }: { series: Point[] }) {
  const [range, setRange] = useState(RANGES[0].s)
  const [showTable, setShowTable] = useState(false)
  const [hover, setHover] = useState<number | null>(null)
  const [ref, width] = useWidth<HTMLDivElement>()

  const now = series.at(-1)?.t ?? 0
  const t0 = now - range
  const data = useMemo(() => series.filter((p) => p.t >= t0), [series, t0])
  const innerW = Math.max(0, width - M.left - M.right)
  const innerH = H - M.top - M.bottom
  const x = (t: number) => M.left + ((t - t0) / range) * innerW
  const y = (v: number) => M.top + (1 - v / 100) * innerH

  const paths = SERIES.map((s) => {
    let d = ''
    let prev: Point | null = null
    for (const p of data) {
      const v = p[s.key]
      if (v == null) {
        prev = null
        continue
      }
      const cmd = prev && p.t - prev.t <= GAP_S ? 'L' : 'M'
      d += `${cmd}${x(p.t).toFixed(1)},${y(v).toFixed(1)}`
      prev = p
    }
    return d
  })

  const ticks = useMemo(() => {
    const step = range <= 300 ? 60 : range <= 900 ? 180 : 600
    const out: number[] = []
    for (let t = Math.ceil(t0 / step) * step; t <= now; t += step) out.push(t)
    return out
  }, [t0, now, range])

  const last = data.at(-1)
  const hovered = hover != null ? data[hover] : null

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!data.length) return
    const rect = e.currentTarget.getBoundingClientRect()
    const t = t0 + ((e.clientX - rect.left - M.left) / innerW) * range
    let lo = 0
    let hi = data.length - 1
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (data[mid].t < t) lo = mid + 1
      else hi = mid
    }
    if (lo > 0 && Math.abs(data[lo - 1].t - t) < Math.abs(data[lo].t - t)) lo--
    setHover(lo)
  }

  // Uç etiketleri üst üste binmesin
  const endLabels = SERIES.map((s) => ({ ...s, v: last?.[s.key] ?? null }))
    .filter((s) => s.v != null)
    .map((s) => ({ ...s, y: y(s.v as number) }))
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < endLabels.length; i++) {
    if (endLabels[i].y - endLabels[i - 1].y < 30) endLabels[i].y = endLabels[i - 1].y + 30
  }

  return (
    <section aria-labelledby="pulse-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="pulse-title" className="display text-xl font-semibold">
            Enerji ve katılım
          </h2>
          <p className="text-sm text-chalk-3">0–100 ölçeğinde, saniyelik ortalama</p>
        </div>
        <div className="flex items-center gap-2">
          <div role="radiogroup" aria-label="Zaman aralığı" className="flex rounded-full bg-sunken p-1">
            {RANGES.map((r) => (
              <button
                key={r.s}
                type="button"
                role="radio"
                aria-checked={range === r.s}
                onClick={() => setRange(r.s)}
                className={clsx(
                  'h-8 rounded-full px-4 text-sm transition-colors',
                  range === r.s ? 'bg-raised text-chalk shadow-sm' : 'text-chalk-2 hover:text-chalk',
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            aria-pressed={showTable}
            onClick={() => setShowTable((v) => !v)}
            className={clsx(
              'inline-flex h-9 items-center gap-1.5 rounded-full px-4 text-sm',
              showTable ? 'bg-sunken text-chalk' : 'text-chalk-3 hover:bg-sunken hover:text-chalk',
            )}
          >
            <Table2 className="size-4" aria-hidden />
            Tablo
          </button>
        </div>
      </div>

      <ul className="flex gap-5 text-sm text-chalk-2" aria-label="Seriler">
        {SERIES.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span className="h-0.5 w-4 rounded-full" style={{ background: s.color }} aria-hidden />
            {s.label}
          </li>
        ))}
      </ul>

      <div ref={ref} className="relative">
        {showTable ? (
          <DataTable data={data} />
        ) : (
          <>
            <svg
              width={width}
              height={H}
              role="img"
              aria-label={`Son ${RANGES.find((r) => r.s === range)?.label} için enerji ve katılım grafiği. Son değerler: enerji ${num(
                last?.energy,
              )}, katılım ${num(last?.engagement)}.`}
              onPointerMove={onMove}
              onPointerLeave={() => setHover(null)}
              className="block touch-none select-none"
            >
              {[0, 25, 50, 75, 100].map((v) => (
                <g key={v}>
                  <line x1={M.left} x2={M.left + innerW} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth={1} />
                  <text x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end" className="numeric fill-chalk-3 text-[11px]">
                    {v}
                  </text>
                </g>
              ))}
              {ticks.map((t) => (
                <text key={t} x={x(t)} y={H - 6} textAnchor="middle" className="numeric fill-chalk-3 text-[11px]">
                  {shortClock(t)}
                </text>
              ))}
              {paths.map((d, i) => (
                <path
                  key={SERIES[i].key}
                  d={d}
                  fill="none"
                  stroke={SERIES[i].color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              ))}
              {last &&
                SERIES.map((s) =>
                  last[s.key] == null ? null : (
                    <circle
                      key={s.key}
                      cx={x(last.t)}
                      cy={y(last[s.key] as number)}
                      r={4}
                      fill={s.color}
                      stroke="var(--board)"
                      strokeWidth={2}
                    />
                  ),
                )}
              {endLabels.map((s) => (
                <text key={s.key} x={M.left + innerW + 10} y={s.y} dy="0.32em" className="fill-chalk-2 text-[12px]">
                  <tspan className="numeric font-semibold fill-chalk">{num(s.v)}</tspan>
                  <tspan dx={4}>{s.label}</tspan>
                </text>
              ))}
              {hovered && (
                <g>
                  <line
                    x1={x(hovered.t)}
                    x2={x(hovered.t)}
                    y1={M.top}
                    y2={M.top + innerH}
                    stroke="var(--chalk-3)"
                    strokeDasharray="2 3"
                  />
                  {SERIES.map((s) =>
                    hovered[s.key] == null ? null : (
                      <circle
                        key={s.key}
                        cx={x(hovered.t)}
                        cy={y(hovered[s.key] as number)}
                        r={5}
                        fill={s.color}
                        stroke="var(--board)"
                        strokeWidth={2}
                      />
                    ),
                  )}
                </g>
              )}
            </svg>
            {!data.length && (
              <p className="absolute inset-0 flex items-center justify-center text-sm text-chalk-3">
                Veri toplandıkça çizgi burada oluşacak.
              </p>
            )}
            {hovered && (
              <div
                className="pointer-events-none absolute top-2 z-10 min-w-36 rounded-lg bg-raised px-3 py-2 text-sm shadow-lg ring-1 ring-line-strong"
                style={{
                  left: Math.min(Math.max(x(hovered.t) + 12, 0), Math.max(0, width - 170)),
                }}
              >
                <p className="numeric text-chalk-3">{clock(hovered.t)}</p>
                {SERIES.map((s) => (
                  <p key={s.key} className="mt-1 flex items-center justify-between gap-4">
                    <span className="flex items-center gap-2 text-chalk-2">
                      <span className="size-2 rounded-full" style={{ background: s.color }} aria-hidden />
                      {s.label}
                    </span>
                    <span className="numeric font-semibold text-chalk">{num(hovered[s.key])}</span>
                  </p>
                ))}
                <p className="mt-1 flex justify-between gap-4 text-chalk-2">
                  Kişi <span className="numeric font-semibold text-chalk">{hovered.count}</span>
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

function DataTable({ data }: { data: Point[] }) {
  // Dakikalık özet: tablo okunabilir kalsın
  const rows = useMemo(() => {
    const byMin = new Map<number, Point[]>()
    for (const p of data) {
      const k = Math.floor(p.t / 60) * 60
      byMin.set(k, [...(byMin.get(k) ?? []), p])
    }
    const avg = (ps: Point[], k: 'energy' | 'engagement') => {
      const v = ps.map((p) => p[k]).filter((x): x is number => x != null)
      return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
    }
    return [...byMin.entries()]
      .map(([t, ps]) => ({ t, energy: avg(ps, 'energy'), engagement: avg(ps, 'engagement'), count: Math.max(...ps.map((p) => p.count)) }))
      .reverse()
  }, [data])
  return (
    <div className="max-h-[220px] overflow-auto rounded-lg ring-1 ring-line">
      <table className="w-full text-sm">
        <caption className="sr-only">Dakikalık ortalama enerji, katılım ve kişi sayısı</caption>
        <thead className="sticky top-0 bg-sunken text-left text-chalk-3">
          <tr>
            <th className="px-3 py-2 font-normal">Dakika</th>
            <th className="px-3 py-2 text-right font-normal">Enerji</th>
            <th className="px-3 py-2 text-right font-normal">Katılım</th>
            <th className="px-3 py-2 text-right font-normal">Kişi</th>
          </tr>
        </thead>
        <tbody className="numeric">
          {rows.map((r) => (
            <tr key={r.t} className="border-t border-line">
              <td className="px-3 py-1.5 text-chalk-2">{shortClock(r.t)}</td>
              <td className="px-3 py-1.5 text-right">{num(r.energy)}</td>
              <td className="px-3 py-1.5 text-right">{num(r.engagement)}</td>
              <td className="px-3 py-1.5 text-right">{r.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
