import { X } from 'lucide-react'
import { num } from '../lib/format'
import type { LabelMeta, Person } from '../lib/types'

/**
 * Seçili kişinin ham sinyalleri. Amaç şeffaflık: kullanıcı her göstergenin hangi ölçümden
 * geldiğini görüp sonucun makul olup olmadığına kendisi karar verebilsin.
 */
export function PersonDetail({
  id,
  person,
  labels,
  onClose,
}: {
  id: number
  person: Person | undefined
  labels: LabelMeta[]
  onClose: () => void
}) {
  const s = person?.signals
  const probs = person?.probs

  return (
    <aside
      aria-label={`Kişi ${id} ayrıntıları`}
      className="z-20 w-full rounded-xl bg-raised/95 p-4 text-sm text-chalk shadow-xl ring-1 ring-line-strong backdrop-blur sm:absolute sm:right-3 sm:top-3 sm:max-h-[calc(100%-1.5rem)] sm:w-72 sm:overflow-y-auto"
    >
      <div className="flex items-center justify-between">
        <h3 className="display text-base font-semibold">Kişi {id}</h3>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex size-8 items-center justify-center rounded-lg text-chalk-3 hover:bg-sunken hover:text-chalk"
          aria-label="Ayrıntıyı kapat"
        >
          <X className="size-4" />
        </button>
      </div>

      {!person ? (
        <p className="mt-2 text-chalk-3">Bu kişi kadrajdan çıktı.</p>
      ) : !s ? (
        <p className="mt-2 text-chalk-3">
          Yüz yeterince net görünmüyor; yalnızca sayımda kullanılıyor. Kişi kameraya dönünce değerler burada belirir.
        </p>
      ) : (
        <>
          <Section title="İfade olasılıkları">
            {probs ? (
              <ul className="flex flex-col gap-1.5">
                {labels.map((l) => {
                  const v = probs[l.key] ?? 0
                  const top = l.key === person.emotion
                  return (
                    <li key={l.key} className="grid grid-cols-[5.5rem_1fr_2.5rem] items-center gap-2">
                      <span className={top ? 'font-semibold text-chalk' : 'text-chalk-2'}>{l.label}</span>
                      <span className="h-1.5 rounded-full bg-sunken" aria-hidden>
                        <span
                          className="block h-full rounded-full"
                          style={{ width: `${Math.max(v * 100, 1)}%`, background: top ? 'var(--bar)' : 'var(--bar-muted)' }}
                        />
                      </span>
                      <span className={`numeric text-right ${top ? 'font-semibold text-chalk' : 'text-chalk-3'}`}>
                        %{num(v * 100)}
                      </span>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-chalk-3">İfade modeli yüklü değil.</p>
            )}
          </Section>

          <Section title="Katılım (öğrenilmiş model)">
            {person.engagement != null ? (
              <>
                <div className="flex items-baseline justify-between">
                  <span className="display text-2xl font-semibold">%{num(person.engagement * 100)}</span>
                  <span className={person.engagement >= 0.5 ? 'text-[var(--tone-positive)]' : 'text-[var(--tone-tired)]'}>
                    {person.engagement >= 0.5 ? 'Katılımcı' : 'Dalgın'}
                  </span>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-sunken" aria-hidden>
                  <div
                    className="h-full rounded-full bg-[var(--series-attention)] transition-[width] duration-500"
                    style={{ width: `${person.engagement * 100}%` }}
                  />
                </div>
              </>
            ) : (
              <p className="text-chalk-3">
                Model ısınıyor: son birkaç saniyelik yüz verisi toplanıyor (%{num((person.engagement_progress ?? 0) * 100)}).
              </p>
            )}
            <p className="mt-2 text-[12px] leading-snug text-chalk-3">
              Çevrimiçi ders videolarıyla (EngageWild) eğitilmiş dikkat ağı; son ~10 saniyedeki yüz ifadesi değişimlerine bakar.
            </p>
          </Section>

          <Section title={`Enerji ${num(person.energy)}`}>
            <Row label="İfadeden uyarılmışlık" value={pct01(s.arousal)} />
            <Row label="Hareket" value={pct01(s.motion)} />
            <Row label="Uyanıklık (gözler açık)" value={pct01(s.alertness)} />
            <Row label="Son 1 dk esneme" value={s.yawn ? 'Var (×0,8)' : 'Yok'} />
            <p className="mt-2 text-[12px] leading-snug text-chalk-3">
              Enerji = (25 + 75 × canlılık) × uyanıklık. Canlılık, uyarılmışlığın %60'ı ile hareketin %40'ıdır.
            </p>
          </Section>

          <Section title="Göz ve baş">
            <Row label="Göz kapanma (30 sn)" value={`%${num(s.perclos * 100)}`} />
            <Row label="Sağa/sola dönüş" value={s.yaw == null ? '—' : `${num(s.yaw)}°`} />
            <Row label="Aşağı/yukarı eğim" value={s.pitch == null ? '—' : `${num(s.pitch)}°`} />
            <Row
              label="Öne dönük"
              value={person.attentive == null ? '—' : person.attentive ? 'Evet' : 'Hayır'}
            />
            <p className="mt-2 text-[12px] leading-snug text-chalk-3">
              Öne dönük sayılmak için dönüş ±25°, eğim −20°'den büyük olmalı.
            </p>
          </Section>
        </>
      )}
    </aside>
  )
}

const pct01 = (v: number | undefined) => (v == null ? '—' : `%${num(v * 100)}`)

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4 border-t border-line pt-3">
      <h4 className="mb-2 font-semibold text-chalk">{title}</h4>
      {children}
    </section>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex items-baseline justify-between gap-3 py-0.5">
      <span className="text-chalk-2">{label}</span>
      <span className="numeric text-chalk">{value}</span>
    </p>
  )
}
