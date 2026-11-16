import clsx from 'clsx'
import { Moon, ShieldCheck, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AtmospherePanel } from './components/Atmosphere'
import { AffectPlane, EmotionBars } from './components/Emotions'
import { PulseChart } from './components/PulseChart'
import { Signals } from './components/Signals'
import { VideoStage } from './components/VideoStage'
import { duration, num } from './lib/format'
import { useLive, useTheme, type Connection } from './lib/live'
import type { EngineStatus, LabelMeta } from './lib/types'

const FALLBACK_LABELS: LabelMeta[] = [
  ['neutral', 'Nötr', 0, 0],
  ['happiness', 'Mutlu', 0.8, 0.45],
  ['surprise', 'Şaşkın', 0.35, 0.8],
  ['sadness', 'Üzgün', -0.7, -0.4],
  ['anger', 'Kızgın', -0.6, 0.7],
  ['disgust', 'Hoşnutsuz', -0.7, 0.3],
  ['fear', 'Endişeli', -0.6, 0.75],
  ['contempt', 'Küçümseyen', -0.5, 0.2],
].map(([key, label, valence, arousal]) => ({ key, label, valence, arousal }) as LabelMeta)

export default function App() {
  const live = useLive()
  const { theme, toggle } = useTheme()
  const labels = live.meta?.labels ?? FALLBACK_LABELS

  return (
    <div className="mx-auto flex min-h-dvh max-w-[1560px] flex-col px-4 sm:px-6 lg:px-10">
      <Header connection={live.connection} status={live.status} theme={theme} onTheme={toggle} />

      <main className="flex flex-1 flex-col gap-10 pb-10">
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.65fr)_minmax(340px,1fr)] xl:gap-12">
          <VideoStage
            connection={live.connection}
            frameUrl={live.frameUrl}
            frameSize={live.frameSize}
            snapshot={live.snapshot}
            status={live.status}
            onPrivacy={live.setPrivacy}
            labels={labels}
          />
          <AtmospherePanel snapshot={live.snapshot} series={live.series} />
        </div>

        <div className="border-t border-line pt-8">
          <PulseChart series={live.series} />
        </div>

        <div className="grid gap-10 border-t border-line pt-8 md:grid-cols-2 xl:grid-cols-[1.1fr_1fr_1fr] xl:gap-12">
          <EmotionBars snapshot={live.snapshot} labels={labels} />
          <AffectPlane snapshot={live.snapshot} series={live.series} labels={labels} />
          <Signals snapshot={live.snapshot} />
        </div>
      </main>

      <Footer status={live.status} />
    </div>
  )
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--board-raised)" stroke="var(--line-strong)" />
      <path
        d="M4 17h6l2.5-6 4 12 3-9 1.8 3H28"
        fill="none"
        stroke="var(--highlight)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Header({
  connection,
  status,
  theme,
  onTheme,
}: {
  connection: Connection
  status: EngineStatus | null
  theme: 'dark' | 'light'
  onTheme: () => void
}) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const sourceLive = status?.source.status === 'live'
  const state =
    connection !== 'open'
      ? { label: connection === 'closed' ? 'Bağlantı yok' : 'Bağlanıyor', color: 'var(--tone-tense)' }
      : !sourceLive
        ? { label: 'Kamera bekleniyor', color: 'var(--tone-tired)' }
        : status?.mode === 'mock'
          ? { label: 'Demo', color: 'var(--highlight)' }
          : { label: 'Canlı', color: 'var(--tone-positive)' }

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 py-6">
      <div className="flex items-center gap-3">
        <Logo />
        <div>
          <h1 className="display text-2xl font-bold leading-none">VibeSight</h1>
          <p className="mt-1 text-sm text-chalk-3">Oda atmosferi, anlık</p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <p className="numeric hidden text-lg text-chalk-2 sm:block" aria-label="Saat">
          {now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
        </p>
        <p
          className="inline-flex h-9 items-center gap-2 rounded-full bg-raised px-3.5 text-sm ring-1 ring-line"
          role="status"
          aria-live="polite"
        >
          <span
            className={clsx('size-2 rounded-full', state.label === 'Canlı' && 'beat')}
            style={{ background: state.color }}
            aria-hidden
          />
          {state.label}
        </p>
        {status && (
          <p className="hidden text-sm text-chalk-3 lg:block" title="Analiz hızı ve bir karenin işlenme süresi">
            <span className="numeric text-chalk-2">{num(status.analysis_fps, 1)}</span> analiz/sn,{' '}
            <span className="numeric text-chalk-2">{num(status.latency_ms)}</span> ms
          </p>
        )}
        <button
          type="button"
          onClick={onTheme}
          className="inline-flex size-9 items-center justify-center rounded-lg text-chalk-2 ring-1 ring-line hover:bg-raised hover:text-chalk"
          aria-label={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
          title={theme === 'dark' ? 'Açık tema' : 'Koyu tema'}
        >
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </div>
    </header>
  )
}

function Footer({ status }: { status: EngineStatus | null }) {
  const emotion = status?.models.emotion
  return (
    <footer className="flex flex-col gap-4 border-t border-line py-6 text-[13px] text-chalk-3 md:flex-row md:items-start md:justify-between">
      <p className="flex max-w-[70ch] gap-2">
        <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          Görüntüler kaydedilmez ve kimse tanınmaz; yalnızca odanın toplu metrikleri bu bilgisayarda saklanır. Yüz ifadeleri
          bir kişinin iç duygusunu kesin olarak göstermez, sonuçları eğilim olarak yorumlayın.
        </span>
      </p>
      {status && (
        <dl className="grid shrink-0 grid-cols-[auto_auto] gap-x-4 gap-y-0.5">
          <dt>İfade modeli</dt>
          <dd className={emotion?.loaded ? 'text-chalk-2' : 'text-[var(--tone-tired)]'}>
            {emotion?.loaded ? emotion.name : 'yüklü değil'}
          </dd>
          <dt>Çalışma süresi</dt>
          <dd className="text-chalk-2">{duration(status.uptime_s)}</dd>
        </dl>
      )}
    </footer>
  )
}
