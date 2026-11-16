import clsx from 'clsx'
import { EyeOff, ScanFace, Square, WifiOff } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Connection } from '../lib/live'
import type { EngineStatus, LabelMeta, Snapshot } from '../lib/types'
import { PersonDetail } from './PersonDetail'

interface Props {
  connection: Connection
  frameUrl: string | null
  frameSize: { w: number; h: number } | null
  snapshot: Snapshot | null
  status: EngineStatus | null
  onPrivacy: (on: boolean) => void
  labels: LabelMeta[]
  className?: string
}

/**
 * Canlı görüntü kartı. Görüntü, oranı bozulmadan kartın içine sığdırılır; kutular ve etiketler
 * aynı çerçeveye yerleştirildiği için her boyutta (projeksiyon, tam ekran) görüntüyle hizalı kalır.
 */
export function VideoStage({ connection, frameUrl, frameSize, snapshot, status, onPrivacy, labels, className }: Props) {
  const [overlay, setOverlay] = useState(true)
  const [selected, setSelected] = useState<number | null>(null)
  const area = useRef<HTMLDivElement>(null)
  const aspect = frameSize ? frameSize.w / frameSize.h : 16 / 9
  const fit = useFitBox(area, aspect)
  const privacy = status?.privacy_blur ?? false
  const source = status?.source
  const live = connection === 'open' && source?.status === 'live' && frameUrl

  return (
    <section aria-label="Canlı görüntü" className={clsx('relative min-h-0', className)}>
      <div
        ref={area}
        className="relative flex h-full min-h-[240px] w-full items-center justify-center overflow-hidden rounded-[1.75rem] bg-[var(--video-bg)] ring-1 ring-white/10"
      >
        <div className="relative" style={{ width: fit.w, height: fit.h }}>
          {frameUrl && (
            <img
              src={frameUrl}
              alt="Kameradan canlı görüntü"
              className={clsx('absolute inset-0 h-full w-full', !live && 'opacity-40 grayscale')}
              draggable={false}
            />
          )}

          {overlay && live && snapshot && (
            <div className="pointer-events-none absolute inset-0">
              {snapshot.people.map((p) => {
                const [x1, y1, x2, y2] = p.box
                const hasFace = p.emotion_label != null
                const isSel = selected === p.id
                return (
                  <div
                    key={p.id}
                    className="absolute transition-[left,top,width,height] duration-150 ease-linear"
                    style={{
                      left: `${x1 * 100}%`,
                      top: `${y1 * 100}%`,
                      width: `${(x2 - x1) * 100}%`,
                      height: `${(y2 - y1) * 100}%`,
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setSelected((cur) => (cur === p.id ? null : p.id))}
                      aria-pressed={isSel}
                      aria-label={`Kişi ${p.id}${p.emotion_label ? `, ${p.emotion_label}` : ''}: ayrıntıları göster`}
                      className={clsx(
                        'pointer-events-auto absolute inset-0 cursor-pointer rounded-2xl transition-[box-shadow,background-color]',
                        isSel
                          ? 'bg-white/10 shadow-[inset_0_0_0_3px_#ffffff]'
                          : hasFace
                            ? 'shadow-[inset_0_0_0_1.5px_rgb(255_255_255/0.85)] hover:bg-white/5'
                            : 'shadow-[inset_0_0_0_1.5px_rgb(255_255_255/0.35)] hover:bg-white/5',
                      )}
                    />
                    {hasFace && (
                      <div className="glass absolute bottom-full left-0 mb-1.5 hidden items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-medium leading-none sm:flex">
                        {p.emotion_label}
                        {p.attentive === false && <EyeOff className="size-3.5 opacity-75" aria-label="Başka yöne bakıyor" />}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {selected != null && live && (
            <div className="hidden sm:block">
              <PersonDetail
                id={selected}
                person={snapshot?.people.find((p) => p.id === selected)}
                labels={labels}
                onClose={() => setSelected(null)}
              />
            </div>
          )}
        </div>

        {!live && <StageMessage connection={connection} sourceStatus={source?.status} hasFrame={!!frameUrl} />}

        {live && (
          <div className="absolute inset-x-4 bottom-4 flex items-end justify-between gap-3">
            <div className="glass flex items-center gap-1 rounded-full p-1" role="group" aria-label="Görüntü seçenekleri">
              <GlassToggle pressed={overlay} onClick={() => setOverlay((v) => !v)} icon={<Square className="size-4" />}>
                Kutular
              </GlassToggle>
              <GlassToggle pressed={privacy} onClick={() => onPrivacy(!privacy)} icon={<ScanFace className="size-4" />}>
                Yüzleri gizle
              </GlassToggle>
            </div>
            <p className="glass hidden rounded-full px-3.5 py-2 text-[13px] text-white/80 md:block">
              {status?.mode === 'mock' ? 'Demo verisi, kamera bağlı değil' : source?.label}
            </p>
          </div>
        )}
      </div>

      {selected != null && live && (
        <div className="mt-4 sm:hidden">
          <PersonDetail
            id={selected}
            person={snapshot?.people.find((p) => p.id === selected)}
            labels={labels}
            onClose={() => setSelected(null)}
          />
        </div>
      )}
    </section>
  )
}

function GlassToggle({
  pressed,
  onClick,
  icon,
  children,
}: {
  pressed: boolean
  onClick: () => void
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={clsx(
        'inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-[14px] font-medium transition-colors',
        pressed ? 'bg-white text-black' : 'text-white/85 hover:bg-white/15',
      )}
    >
      {icon}
      {children}
    </button>
  )
}

function StageMessage({
  connection,
  sourceStatus,
  hasFrame,
}: {
  connection: Connection
  sourceStatus?: string
  hasFrame: boolean
}) {
  let title = 'Bağlanılıyor'
  let body = 'Analiz sunucusu başlatılıyor. Birkaç saniye sürebilir.'
  if (connection === 'closed') {
    title = 'Sunucuya ulaşılamıyor'
    body = "PowerShell'de .\\vs.ps1 dev komutunu çalıştırın; bağlantı kendiliğinden yenilenecek."
  } else if (connection === 'open' && sourceStatus === 'reconnecting') {
    title = 'Kameraya yeniden bağlanılıyor'
    body = 'Kamera ile aynı Wi-Fi ağında olduğunuzu ve .env dosyasındaki IP, kullanıcı adı ve şifreyi kontrol edin.'
  } else if (connection === 'open') {
    title = 'Görüntü bekleniyor'
    body = 'Kaynak açıldı, ilk kare geliyor.'
  }
  return (
    <div
      className={clsx(
        'absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center',
        hasFrame && 'bg-black/60',
      )}
      role="status"
    >
      {connection === 'closed' || sourceStatus === 'reconnecting' ? (
        <WifiOff className="size-7 text-white/60" aria-hidden />
      ) : (
        <span className="beat block size-3 rounded-full bg-white/80" aria-hidden />
      )}
      <p className="display text-2xl font-semibold text-white">{title}</p>
      <p className="max-w-md text-[15px] text-white/65">{body}</p>
    </div>
  )
}

/** Görüntüyü oranını bozmadan alana sığdırır (kutular görüntüyle hizalı kalsın). */
function useFitBox(area: React.RefObject<HTMLElement | null>, aspect: number) {
  const [box, setBox] = useState({ w: 0, h: 0 })
  useEffect(() => {
    if (!area.current) return
    const el = area.current
    const update = () => {
      const w = el.clientWidth
      const h = el.clientHeight
      if (!w || !h) return
      setBox(w / h > aspect ? { w: h * aspect, h } : { w, h: w / aspect })
    }
    const ro = new ResizeObserver(update)
    ro.observe(el)
    update()
    return () => ro.disconnect()
  }, [area, aspect])
  return box
}
