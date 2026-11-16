import { BatteryMedium, Coffee, Flame, Focus, HelpCircle, Smile, Users, Waves, Zap } from 'lucide-react'
import { energyWord, num, toneVar } from '../lib/format'
import type { LabelMeta, Point, Snapshot, Tone } from '../lib/types'

const TONE_ICON: Record<Tone, typeof Smile> = {
  positive: Smile,
  focused: Focus,
  calm: Waves,
  tired: Coffee,
  tense: Flame,
  unknown: HelpCircle,
}

/**
 * Canlı sahnenin sağ kolonu: projeksiyonda birkaç metreden okunabilecek, her an görünen durum özeti.
 * Sıra okunma önceliğidir: ortamın havası → üç ana sayı → baskın ifadeler → son 5 dakika.
 */
export function LiveRail({
  snapshot,
  series,
  labels,
}: {
  snapshot: Snapshot | null
  series: Point[]
  labels: LabelMeta[]
}) {
  return (
    <aside
      aria-label="Canlı durum"
      tabIndex={0}
      className="flex min-h-0 flex-col gap-4 overflow-y-auto rounded-[1.5rem] lg:h-full"
    >
      <Mood snapshot={snapshot} series={series} />
      <Numbers snapshot={snapshot} />
      <Expressions snapshot={snapshot} labels={labels} />
      <Trend series={series} />
    </aside>
  )
}

function Mood({ snapshot, series }: { snapshot: Snapshot | null; series: Point[] }) {
  const a = snapshot?.atmosphere
  const tone: Tone = a?.tone ?? 'unknown'
  const Icon = TONE_ICON[tone]
  return (
    <section className="card shrink-0 px-7 pb-5 pt-6" aria-live="polite" aria-labelledby="mood-title">
      <h2 id="mood-title" className="flex items-center gap-2 text-[15px] font-medium text-chalk-3">
        <Icon className="size-4" style={{ color: toneVar(tone) }} aria-hidden />
        Ortamın havası
      </h2>
      <p
        className="display mt-2 text-[clamp(2.5rem,3.4vw,3.75rem)] font-semibold leading-[1.02]"
        style={{ color: toneVar(tone) }}
      >
        {a?.label ?? 'Bekleniyor'}
      </p>
      <p className="mt-3 text-[17px] leading-snug text-chalk-2">
        {a?.description ?? 'Kamerada yüz göründüğünde ortamın genel durumu burada belirir.'}
      </p>
      <Ribbon series={series} />
    </section>
  )
}

const TONE_OF: Record<string, Tone> = {
  positive: 'positive',
  focused: 'focused',
  balanced: 'focused',
  calm: 'calm',
  tired: 'tired',
  distracted: 'tired',
  tense: 'tense',
  unknown: 'unknown',
}
const RIBBON_S = 15 * 60
const RIBBON_BINS = 30

/** Son 15 dakikada ortamın havası: her dilim 30 sn, en sık görülen ton. */
function Ribbon({ series }: { series: Point[] }) {
  const end = series.at(-1)?.t
  if (end == null) return null
  const start = end - RIBBON_S
  const votes = Array.from({ length: RIBBON_BINS }, () => new Map<Tone, number>())
  for (const p of series) {
    if (p.t < start || !p.atmosphere) continue
    const i = Math.min(RIBBON_BINS - 1, Math.floor(((p.t - start) / RIBBON_S) * RIBBON_BINS))
    const tone = TONE_OF[p.atmosphere] ?? 'unknown'
    votes[i].set(tone, (votes[i].get(tone) ?? 0) + 1)
  }
  const bins = votes.map((m) => [...m.entries()].sort((x, y) => y[1] - x[1])[0]?.[0] ?? null)
  return (
    <figure className="mt-5">
      <div className="flex h-1.5 gap-[3px]" role="img" aria-label="Son 15 dakikada ortamın havası">
        {bins.map((tone, i) => (
          <span
            key={i}
            className="flex-1 rounded-full"
            style={{ background: tone ? toneVar(tone) : 'var(--board-sunken)' }}
          />
        ))}
      </div>
      <figcaption className="mt-2 flex justify-between text-[13px] text-chalk-3">
        <span>15 dk önce</span>
        <span>şimdi</span>
      </figcaption>
    </figure>
  )
}

function Numbers({ snapshot }: { snapshot: Snapshot | null }) {
  const eng = snapshot?.engagement
  return (
    <section className="card shrink-0 px-7 py-1" aria-label="Ana göstergeler">
      <div className="divide-y divide-line">
        <Row
          icon={<Users className="size-[18px]" aria-hidden />}
          label="Kişi"
          value={snapshot ? String(snapshot.count) : '—'}
          note={snapshot ? `${snapshot.faces_analyzed} yüz analiz ediliyor` : undefined}
        />
        <Row
          icon={<Zap className="size-[18px]" aria-hidden />}
          label="Enerji"
          value={num(snapshot?.energy)}
          note={energyWord(snapshot?.energy)}
          meter={snapshot?.energy}
          color="var(--series-energy)"
        />
        <Row
          icon={<BatteryMedium className="size-[18px]" aria-hidden />}
          label="Katılım"
          value={eng == null ? '—' : `%${num(eng * 100)}`}
          note={eng == null ? 'Model ısınıyor' : eng >= 0.5 ? 'Çoğunluk katılımcı' : 'Çoğunluk dalgın'}
          meter={eng == null ? null : eng * 100}
          color="var(--series-attention)"
        />
      </div>
    </section>
  )
}

function Row({
  icon,
  label,
  value,
  note,
  meter,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string
  note?: string
  meter?: number | null
  color?: string
}) {
  return (
    <div className="py-3.5">
      <div className="flex items-baseline justify-between gap-4">
        <p className="flex items-center gap-2 text-[17px] text-chalk-2">
          <span className="text-chalk-3">{icon}</span>
          {label}
        </p>
        <p className="numeric text-[2.25rem] font-semibold leading-none text-chalk" aria-label={`${label}: ${value}`}>
          {value}
        </p>
      </div>
      {meter !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
          <div
            className="h-full rounded-full transition-[width] duration-700 ease-out"
            style={{ width: `${Math.max(0, Math.min(100, meter ?? 0))}%`, background: color }}
          />
        </div>
      )}
      {note && <p className="mt-1.5 text-[14px] text-chalk-3">{note}</p>}
    </div>
  )
}

function Expressions({ snapshot, labels }: { snapshot: Snapshot | null; labels: LabelMeta[] }) {
  const name = (key: string) => labels.find((l) => l.key === key)?.label ?? key
  const top = snapshot?.emotions
    ? Object.entries(snapshot.emotions)
        .sort((x, y) => y[1] - x[1])
        .slice(0, 3)
    : []
  return (
    <section className="card shrink-0 px-7 py-5" aria-labelledby="expr-title">
      <h2 id="expr-title" className="text-[15px] font-medium text-chalk-3">
        Baskın ifadeler
      </h2>
      {top.length ? (
        <ul className="mt-3 flex flex-col gap-3">
          {top.map(([key, v], i) => (
            <li key={key}>
              <div className="flex items-baseline justify-between text-[17px]">
                <span className={i === 0 ? 'font-semibold text-chalk' : 'text-chalk-2'}>{name(key)}</span>
                <span className={`numeric ${i === 0 ? 'font-semibold text-chalk' : 'text-chalk-3'}`}>
                  %{num(v * 100)}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
                <div
                  className="h-full rounded-full transition-[width] duration-500 ease-out"
                  style={{ width: `${Math.max(v * 100, 1)}%`, background: i === 0 ? 'var(--bar)' : 'var(--bar-muted)' }}
                />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-[15px] text-chalk-3">Yüz göründüğünde burada belirir.</p>
      )}
    </section>
  )
}

const SPARK_S = 5 * 60
const W = 340
const H = 96

function Trend({ series }: { series: Point[] }) {
  const end = series.at(-1)?.t
  if (end == null) return null
  const t0 = end - SPARK_S
  const pts = series.filter((p) => p.t >= t0)
  const x = (t: number) => ((t - t0) / SPARK_S) * W
  const y = (v: number) => 4 + (1 - v / 100) * (H - 8)
  const path = (key: 'energy' | 'engagement') => {
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
    <section className="card flex min-h-[150px] flex-1 flex-col px-7 py-5" aria-labelledby="trend-title">
      <div className="flex items-baseline justify-between">
        <h2 id="trend-title" className="text-[15px] font-medium text-chalk-3">
          Son 5 dakika
        </h2>
        <ul className="flex gap-4 text-[13px] text-chalk-3" aria-label="Seriler">
          <li className="flex items-center gap-1.5">
            <span className="h-[3px] w-3.5 rounded-full bg-[var(--series-energy)]" aria-hidden />
            Enerji
          </li>
          <li className="flex items-center gap-1.5">
            <span className="h-[3px] w-3.5 rounded-full bg-[var(--series-attention)]" aria-hidden />
            Katılım
          </li>
        </ul>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="mt-3 block min-h-0 w-full flex-1" role="img" aria-label="Son 5 dakikada enerji ve katılım">
        <line x1={0} x2={W} y1={y(50)} y2={y(50)} stroke="var(--line)" strokeDasharray="2 4" vectorEffect="non-scaling-stroke" />
        <path d={path('engagement')} fill="none" stroke="var(--series-attention)" strokeWidth={2.25} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
        <path d={path('energy')} fill="none" stroke="var(--series-energy)" strokeWidth={2.25} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </section>
  )
}
