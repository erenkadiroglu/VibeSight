import clsx from 'clsx'
import { EyeOff, Maximize2, ScanFace, Square, Video, WifiOff } from 'lucide-react'
import { useRef, useState } from 'react'
import type { Connection } from '../lib/live'
import { num } from '../lib/format'
import type { EngineStatus, Snapshot } from '../lib/types'

interface Props {
  connection: Connection
  frameUrl: string | null
  frameSize: { w: number; h: number } | null
  snapshot: Snapshot | null
  status: EngineStatus | null
  onPrivacy: (on: boolean) => void
}

export function VideoStage({ connection, frameUrl, frameSize, snapshot, status, onPrivacy }: Props) {
  const [overlay, setOverlay] = useState(true)
  const stage = useRef<HTMLDivElement>(null)
  const aspect = frameSize ? frameSize.w / frameSize.h : 16 / 9
  const privacy = status?.privacy_blur ?? false
  const source = status?.source
  const live = connection === 'open' && source?.status === 'live' && frameUrl

  return (
    <section aria-label="Canlı görüntü" className="flex flex-col gap-3">
      <div
        ref={stage}
        className="relative w-full overflow-hidden rounded-2xl bg-[var(--video-bg)] ring-1 ring-line"
        style={{ aspectRatio: aspect }}
      >
        {frameUrl && (
          <img
            src={frameUrl}
            alt="Kameradan canlı görüntü"
            className={clsx('absolute inset-0 h-full w-full object-cover', !live && 'opacity-40 grayscale')}
            draggable={false}
          />
        )}

        {overlay && live && snapshot && (
          <div className="pointer-events-none absolute inset-0" aria-hidden>
            {snapshot.people.map((p) => {
              const [x1, y1, x2, y2] = p.box
              const hasFace = p.emotion_label != null
              const compact = x2 - x1 < 0.09
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
                  <div
                    className={clsx(
                      'absolute inset-0 rounded-md border',
                      hasFace ? 'border-white/80' : 'border-dashed border-white/45',
                    )}
                  />
                  <div className="absolute bottom-full left-0 mb-1 hidden items-center sm:flex gap-1.5 whitespace-nowrap rounded-md bg-[var(--overlay-ink)]/85 px-1.5 py-0.5 text-[11px] leading-4 text-white/95 backdrop-blur-sm">
                    <span className="numeric text-white/60">{p.id}</span>
                    {hasFace ? (
                      <>
                        <span className="font-semibold">{p.emotion_label}</span>
                        {p.energy != null && !compact && <EnergyPip value={p.energy} />}
                        {p.attentive === false && <EyeOff className="size-3 text-white/70" aria-label="Başka yöne bakıyor" />}
                      </>
                    ) : (
                      <span className="text-white/60">{compact ? 'yüz yok' : 'yüz görünmüyor'}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {!live && <StageMessage connection={connection} sourceStatus={source?.status} hasFrame={!!frameUrl} />}

        {live && status?.mode === 'mock' && (
          <div className="absolute left-3 top-3 rounded-full bg-[var(--overlay-ink)]/80 px-3 py-1 text-xs font-semibold text-[#f2d16b] ring-1 ring-[#f2d16b]/40">
            Demo verisi, kamera bağlı değil
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-sm text-chalk-2">
        <div className="flex min-w-0 items-center gap-2">
          <Video className="size-4 shrink-0 text-chalk-3" aria-hidden />
          <span className="truncate">{source?.label ?? 'Kaynak bekleniyor'}</span>
          {source?.resolution && (
            <span className="numeric shrink-0 text-chalk-3">
              {source.resolution[0]}×{source.resolution[1]}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Görüntü seçenekleri">
          <ToggleButton pressed={overlay} onClick={() => setOverlay((v) => !v)} icon={<Square className="size-4" />}>
            Kutular
          </ToggleButton>
          <ToggleButton pressed={privacy} onClick={() => onPrivacy(!privacy)} icon={<ScanFace className="size-4" />}>
            Yüzleri gizle
          </ToggleButton>
          <button
            type="button"
            onClick={() => void stage.current?.requestFullscreen?.()}
            className="inline-flex size-9 items-center justify-center rounded-lg text-chalk-2 hover:bg-raised hover:text-chalk"
            aria-label="Tam ekran"
            title="Tam ekran"
          >
            <Maximize2 className="size-4" />
          </button>
        </div>
      </div>
    </section>
  )
}

function EnergyPip({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-1" title={`Enerji ${num(value)}`}>
      <span className="relative h-1.5 w-8 overflow-hidden rounded-full bg-white/20">
        <span className="absolute inset-y-0 left-0 rounded-full bg-[#e0b23a]" style={{ width: `${value}%` }} />
      </span>
      <span className="numeric text-white/75">{num(value)}</span>
    </span>
  )
}

function ToggleButton({
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
        'inline-flex h-9 items-center gap-1.5 rounded-lg px-3 transition-colors',
        pressed ? 'bg-raised text-chalk ring-1 ring-line-strong' : 'text-chalk-2 hover:bg-raised hover:text-chalk',
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
  let title = 'Sunucuya bağlanılıyor'
  let body = 'Analiz sunucusu başlatılıyor. Birkaç saniye sürebilir.'
  if (connection === 'closed') {
    title = 'Sunucuya ulaşılamıyor'
    body = 'Arka uç çalışmıyor olabilir. Terminalde `make dev` komutunu çalıştırın; bağlantı otomatik yenilenecek.'
  } else if (connection === 'open' && sourceStatus === 'reconnecting') {
    title = 'Kameraya yeniden bağlanılıyor'
    body = 'Kamera ile aynı Wi-Fi ağında olduğunuzu ve .env dosyasındaki IP, kullanıcı adı ve şifrenin doğru olduğunu kontrol edin.'
  } else if (connection === 'open') {
    title = 'Görüntü bekleniyor'
    body = 'Kaynak açıldı, ilk kare geliyor.'
  }
  return (
    <div
      className={clsx(
        'absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center',
        hasFrame && 'bg-[var(--video-bg)]/60',
      )}
      role="status"
    >
      {connection === 'closed' || sourceStatus === 'reconnecting' ? (
        <WifiOff className="size-7 text-white/60" aria-hidden />
      ) : (
        <span className="beat block size-3 rounded-full bg-[#f2d16b]" aria-hidden />
      )}
      <p className="display text-xl font-semibold text-white/90">{title}</p>
      <p className="max-w-md text-sm text-white/65">{body}</p>
    </div>
  )
}
