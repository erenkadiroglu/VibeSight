import { Activity, Eye, Focus, ScanFace, Wind } from 'lucide-react'
import { num } from '../lib/format'
import type { Snapshot } from '../lib/types'

/** Enerji endeksini oluşturan ham sinyaller — kullanıcı endeksin neden düştüğünü görebilsin. */
export function Signals({ snapshot }: { snapshot: Snapshot | null }) {
  const coverage = snapshot && snapshot.count ? snapshot.faces_analyzed / snapshot.count : null
  const rows = [
    {
      icon: Eye,
      label: 'Göz kapanma oranı',
      hint: 'Son 30 sn içinde gözlerin kapalı olduğu zaman (PERCLOS). %15 üzeri yorgunluk işaretidir.',
      value: snapshot?.perclos == null ? '—' : `%${num(snapshot.perclos * 100)}`,
      meter: snapshot?.perclos == null ? null : Math.min(1, snapshot.perclos / 0.4),
      warn: (snapshot?.perclos ?? 0) >= 0.15,
    },
    {
      icon: Wind,
      label: 'Esneyen kişi',
      hint: 'Son 1 dakikada esneme gözlenen kişi sayısı.',
      value: snapshot ? String(snapshot.yawns_recent) : '—',
      meter: snapshot && snapshot.faces_analyzed ? snapshot.yawns_recent / snapshot.faces_analyzed : null,
      warn: (snapshot?.yawns_recent ?? 0) >= 2,
    },
    {
      icon: Focus,
      label: 'Öne dönük yüzler',
      hint: 'Baş açısı ±25° içinde olan yüzlerin oranı (geometrik ölçüm, katılım modelinden bağımsız).',
      value: snapshot?.attention == null ? '—' : `%${num(snapshot.attention * 100)}`,
      meter: snapshot?.attention ?? null,
      warn: snapshot?.attention != null && snapshot.attention < 0.5,
    },
    {
      icon: Activity,
      label: 'Hareketlilik',
      hint: 'Kişi kutuları içindeki ortalama hareket miktarı.',
      value: num(snapshot?.activity),
      meter: snapshot?.activity == null ? null : snapshot.activity / 100,
      warn: false,
    },
    {
      icon: ScanFace,
      label: 'Analiz kapsamı',
      hint: 'Yüzü yeterince net görünen kişilerin oranı. Düşükse kamerayı yaklaştırın.',
      value: snapshot ? `${snapshot.faces_analyzed}/${snapshot.count}` : '—',
      meter: coverage,
      warn: coverage != null && coverage < 0.5,
    },
  ]
  return (
    <section aria-labelledby="signals-title" className="flex flex-col gap-4">
      <div>
        <h2 id="signals-title" className="display text-xl font-semibold">
          Sinyaller
        </h2>
        <p className="text-sm text-chalk-3">Enerji ve katılımın dayandığı ölçümler</p>
      </div>
      <ul className="flex flex-col divide-y divide-line">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-3 py-3 first:pt-0" title={r.hint}>
            <r.icon className="size-4 shrink-0 text-chalk-3" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-chalk-2">{r.label}</p>
              <p className="sr-only">{r.hint}</p>
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-sunken" aria-hidden>
                <div
                  className="h-full rounded-full transition-[width] duration-500"
                  style={{
                    width: `${Math.round((r.meter ?? 0) * 100)}%`,
                    background: r.warn ? 'var(--tone-tired)' : 'var(--chalk-3)',
                  }}
                />
              </div>
            </div>
            <span className="numeric w-14 text-right text-lg font-semibold text-chalk">{r.value}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
