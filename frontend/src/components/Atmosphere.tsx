import { BatteryLow, Coffee, Flame, Focus, HelpCircle, Smile, Users, Waves } from 'lucide-react'
import { energyWord, num, toneVar } from '../lib/format'
import type { Point, Snapshot, Tone } from '../lib/types'

const TONE_ICON: Record<Tone, typeof Smile> = {
  positive: Smile,
  focused: Focus,
  calm: Waves,
  tired: Coffee,
  tense: Flame,
  unknown: HelpCircle,
}

export function AtmospherePanel({ snapshot, series }: { snapshot: Snapshot | null; series: Point[] }) {
  const a = snapshot?.atmosphere
  const tone: Tone = a?.tone ?? 'unknown'
  const Icon = TONE_ICON[tone]
  const coverage = snapshot && snapshot.count > 0 ? snapshot.faces_analyzed / snapshot.count : null

  return (
    <section aria-labelledby="atmosphere-title" className="flex h-full flex-col">
      <h2 id="atmosphere-title" className="text-sm text-chalk-3">
        Ortamın şu anki havası
      </h2>
      <div className="mt-2 flex items-start gap-3" aria-live="polite">
        <span
          className="mt-2 inline-flex size-10 shrink-0 items-center justify-center rounded-full"
          style={{ background: `color-mix(in oklab, ${toneVar(tone)} 18%, transparent)`, color: toneVar(tone) }}
        >
          <Icon className="size-5" aria-hidden />
        </span>
        <p className="display text-[clamp(2.25rem,4vw,3.5rem)] font-semibold leading-[1.02]" style={{ color: toneVar(tone) }}>
          {a?.label ?? 'Bağlanıyor'}
        </p>
      </div>
      <p className="mt-3 max-w-[38ch] text-[15px] leading-relaxed text-chalk-2">
        {a?.description ?? 'Canlı veri geldiğinde odanın genel durumu burada görünecek.'}
      </p>

      <AtmosphereRibbon series={series} />

      <dl className="grid grid-cols-3 gap-0 pt-10">
        <Reading
          icon={<Users className="size-4" aria-hidden />}
          label="Kişi"
          value={snapshot ? String(snapshot.count) : '—'}
          note={snapshot ? `En yüksek ${snapshot.peak_count}` : undefined}
        />
        <Reading
          icon={<BatteryLow className="size-4" aria-hidden />}
          label="Enerji"
          value={num(snapshot?.energy)}
          note={energyWord(snapshot?.energy)}
          meter={snapshot?.energy}
          meterColor="var(--series-energy)"
        />
        <Reading
          icon={<Focus className="size-4" aria-hidden />}
          label="Dikkat"
          value={snapshot?.attention == null ? '—' : `%${num(snapshot.attention * 100)}`}
          note="öne dönük yüzler"
          meter={snapshot?.attention == null ? null : snapshot.attention * 100}
          meterColor="var(--series-attention)"
        />
      </dl>

      {snapshot && (
        <p className="mt-4 text-[13px] text-chalk-3">
          {snapshot.count === 0
            ? 'Kadrajda kimse yok.'
            : `${snapshot.count} kişiden ${snapshot.faces_analyzed} kişinin yüzü analiz ediliyor${
                coverage != null && coverage < 0.6 ? '. Uzak veya arkası dönük kişiler sayılır ama ifadeleri ölçülmez.' : '.'
              }`}
        </p>
      )}
    </section>
  )
}

function Reading({
  icon,
  label,
  value,
  note,
  meter,
  meterColor,
}: {
  icon: React.ReactNode
  label: string
  value: string
  note?: string
  meter?: number | null
  meterColor?: string
}) {
  return (
    <div className="border-l border-line pl-4 first:border-l-0 first:pl-0">
      <dt className="flex items-center gap-1.5 text-sm text-chalk-3">
        {icon}
        {label}
      </dt>
      <dd className="numeric mt-1 text-4xl font-semibold leading-none text-chalk">{value}</dd>
      {meter !== undefined && (
        <dd className="mt-3 h-1 w-full max-w-24 overflow-hidden rounded-full bg-line" aria-hidden>
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${Math.max(0, Math.min(100, meter ?? 0))}%`, background: meterColor }}
          />
        </dd>
      )}
      {note && <dd className="mt-2 text-[13px] text-chalk-3">{note}</dd>}
    </div>
  )
}

const TONE_OF: Record<string, Tone> = {
  positive: 'positive',
  focused: 'focused',
  balanced: 'focused',
  calm: 'calm',
  tired: 'tired',
  tense: 'tense',
  unknown: 'unknown',
}
const TONE_NAME: Record<Tone, string> = {
  positive: 'Pozitif',
  focused: 'Odaklı / dengeli',
  calm: 'Sakin',
  tired: 'Yorgun',
  tense: 'Gergin',
  unknown: 'Veri yok',
}
const RIBBON_S = 15 * 60
const RIBBON_BINS = 45

/** Son 15 dakikada atmosferin nasıl değiştiğini gösteren şerit (her dilim 20 sn, en sık görülen ton). */
function AtmosphereRibbon({ series }: { series: Point[] }) {
  const end = series.at(-1)?.t
  if (end == null) return null
  const start = end - RIBBON_S
  const bins: (Tone | null)[] = Array.from({ length: RIBBON_BINS }, () => null)
  const votes: Map<Tone, number>[] = bins.map(() => new Map())
  for (const p of series) {
    if (p.t < start || !p.atmosphere) continue
    const i = Math.min(RIBBON_BINS - 1, Math.floor(((p.t - start) / RIBBON_S) * RIBBON_BINS))
    const tone = TONE_OF[p.atmosphere] ?? 'unknown'
    votes[i].set(tone, (votes[i].get(tone) ?? 0) + 1)
  }
  votes.forEach((m, i) => {
    let best: Tone | null = null
    let n = 0
    m.forEach((c, t) => {
      if (c > n) [best, n] = [t, c]
    })
    bins[i] = best
  })
  const present = [...new Set(bins.filter((b): b is Tone => b != null))]

  return (
    <figure className="mt-8">
      <figcaption className="flex items-baseline justify-between text-sm text-chalk-3">
        <span>Son 15 dakika</span>
        <span className="text-[12px]">şimdi</span>
      </figcaption>
      <div className="mt-2 flex h-7 gap-[2px]" role="img" aria-label={`Son 15 dakikadaki atmosfer: ${present.map((t) => TONE_NAME[t]).join(', ')}`}>
        {bins.map((tone, i) => (
          <span
            key={i}
            className="flex-1 rounded-[3px] first:rounded-l-md last:rounded-r-md"
            style={{ background: tone ? toneVar(tone) : 'var(--board-sunken)', opacity: tone ? 0.85 : 1 }}
          />
        ))}
      </div>
      {present.length > 0 && (
        <ul className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-chalk-2">
          {present.map((t) => (
            <li key={t} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-[3px]" style={{ background: toneVar(t) }} aria-hidden />
              {TONE_NAME[t]}
            </li>
          ))}
        </ul>
      )}
    </figure>
  )
}
