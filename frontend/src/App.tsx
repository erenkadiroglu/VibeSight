import clsx from 'clsx'
import { Maximize, Moon, ShieldCheck, Sun } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { AffectPlane, EmotionBars } from './components/Emotions'
import { LiveRail } from './components/LiveRail'
import { PulseChart } from './components/PulseChart'
import { Signals } from './components/Signals'
import { VideoStage } from './components/VideoStage'
import { num } from './lib/format'
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

type View = 'live' | 'details'

export default function App() {
  const live = useLive()
  const { theme, toggle } = useTheme()
  const [view, setView] = useState<View>('live')
  const stageRef = useRef<HTMLDivElement>(null)
  const presenting = usePresentation(stageRef, () => setView('live'))
  const labels = live.meta?.labels ?? FALLBACK_LABELS

  return (
    <div className="flex min-h-dvh flex-col bg-board text-chalk">
      <Header
        connection={live.connection}
        status={live.status}
        view={view}
        onView={setView}
        theme={theme}
        onTheme={toggle}
        onPresent={presenting.toggle}
      />

      {view === 'live' ? (
        <main
          ref={stageRef}
          className={clsx(
            'grid gap-4 bg-board px-4 pb-4 sm:px-6 sm:pb-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,26rem)] lg:grid-rows-[minmax(0,1fr)]',
            presenting.active ? 'h-dvh p-6 sm:p-6' : 'lg:h-[calc(100dvh-4.5rem)]',
          )}
        >
          <VideoStage
            className="aspect-video lg:aspect-auto lg:h-full"
            connection={live.connection}
            frameUrl={live.frameUrl}
            frameSize={live.frameSize}
            snapshot={live.snapshot}
            status={live.status}
            onPrivacy={live.setPrivacy}
            labels={labels}
          />
          <LiveRail snapshot={live.snapshot} series={live.series} labels={labels} />
        </main>
      ) : (
        <Details live={live} labels={labels} />
      )}
    </div>
  )
}

function Details({ live, labels }: { live: ReturnType<typeof useLive>; labels: LabelMeta[] }) {
  return (
    <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 px-4 pb-10 sm:px-6">
      <section className="card p-6 sm:p-8">
        <PulseChart series={live.series} />
      </section>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <section className="card p-6 sm:p-8">
          <EmotionBars snapshot={live.snapshot} labels={labels} />
        </section>
        <section className="card p-6 sm:p-8">
          <AffectPlane snapshot={live.snapshot} series={live.series} labels={labels} />
        </section>
        <section className="card p-6 sm:p-8">
          <Signals snapshot={live.snapshot} />
        </section>
      </div>
      <div className="grid items-start gap-4 md:grid-cols-[1fr_1fr]">
        {live.status && <Models status={live.status} />}
        <section className="card flex gap-3 p-6 text-[15px] leading-relaxed text-chalk-2 sm:p-8">
          <ShieldCheck className="mt-1 size-5 shrink-0 text-chalk-3" aria-hidden />
          <p>
            Görüntüler kaydedilmez ve kimse tanınmaz; yalnızca odanın toplu metrikleri bu bilgisayarda saklanır. Yüz
            ifadeleri bir kişinin iç duygusunu kesin olarak göstermez, sonuçları eğilim olarak yorumlayın.
          </p>
        </section>
      </div>
    </main>
  )
}

function Header({
  connection,
  status,
  view,
  onView,
  theme,
  onTheme,
  onPresent,
}: {
  connection: Connection
  status: EngineStatus | null
  view: View
  onView: (v: View) => void
  theme: 'dark' | 'light'
  onTheme: () => void
  onPresent: () => void
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
          ? { label: 'Demo', color: 'var(--tone-tired)' }
          : { label: 'Canlı', color: 'var(--tone-positive)' }

  return (
    <header className="grid h-[4.5rem] shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 sm:px-6">
      <div className="flex items-center gap-2.5">
        <Logo />
        <h1 className="display text-[19px] font-semibold">VibeSight</h1>
      </div>

      <nav aria-label="Görünüm" className="flex rounded-full bg-sunken p-1">
        {(
          [
            ['live', 'Canlı'],
            ['details', 'Ayrıntılar'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-current={view === key ? 'page' : undefined}
            onClick={() => onView(key)}
            className={clsx(
              'h-8 rounded-full px-5 text-[14px] font-medium transition-colors',
              view === key ? 'bg-raised text-chalk shadow-sm' : 'text-chalk-2 hover:text-chalk',
            )}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="flex items-center justify-end gap-2 sm:gap-3">
        <p className="hidden items-center gap-2 text-[14px] text-chalk-2 md:flex" role="status" aria-live="polite">
          <span
            className={clsx('size-2 rounded-full', state.label === 'Canlı' && 'beat')}
            style={{ background: state.color }}
            aria-hidden
          />
          {state.label}
        </p>
        <p className="numeric hidden text-[15px] text-chalk-2 lg:block" aria-label="Saat">
          {now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
        </p>
        {status && <Performance status={status} />}
        <IconButton label={theme === 'dark' ? 'Açık görünüm' : 'Koyu görünüm'} onClick={onTheme}>
          {theme === 'dark' ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
        </IconButton>
        <button
          type="button"
          onClick={onPresent}
          className="inline-flex h-9 items-center gap-1.5 rounded-full bg-chalk px-4 text-[14px] font-medium text-board transition-opacity hover:opacity-85"
          title="Projeksiyon için tam ekran (kısayol: F)"
        >
          <Maximize className="size-4" aria-hidden />
          Sunum
        </button>
      </div>
    </header>
  )
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="inline-flex size-9 items-center justify-center rounded-full text-chalk-2 transition-colors hover:bg-sunken hover:text-chalk"
    >
      {children}
    </button>
  )
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--chalk)" />
      <path
        d="M5 17h5.5l2.5-6 4 12 3-9 1.8 3H27"
        fill="none"
        stroke="var(--board-raised)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** Sunum (projeksiyon) modu: canlı sahne tam ekran; F kısayolu, Esc ile çıkış. */
function usePresentation(target: React.RefObject<HTMLElement | null>, beforeEnter: () => void) {
  const [active, setActive] = useState(false)
  useEffect(() => {
    const onChange = () => setActive(!!document.fullscreenElement && document.fullscreenElement === target.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [target])
  const toggle = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
      return
    }
    beforeEnter()
    // Canlı görünüm henüz çizilmediyse bir kare bekle
    requestAnimationFrame(() => void target.current?.requestFullscreen?.())
  }, [target, beforeEnter])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      if (e.key.toLowerCase() !== 'f' || e.ctrlKey || e.metaKey || e.altKey) return
      if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))) return
      toggle()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle])
  return { active, toggle }
}

const STAGES: [string, string][] = [
  ['detect', 'Kişi tespiti'],
  ['track', 'Takip'],
  ['face', 'Yüz noktaları'],
  ['emotion', 'İfade modeli'],
  ['engagement', 'Katılım modeli'],
]

/** Üst çubukta hız özeti; tıklanınca her aşamanın süresi. */
function Performance({ status }: { status: EngineStatus }) {
  const t = status.timings_ms ?? {}
  return (
    <details className="relative hidden xl:block">
      <summary className="flex h-9 cursor-pointer list-none items-center rounded-full px-3 text-[14px] text-chalk-3 hover:bg-sunken hover:text-chalk">
        <span className="numeric">{num(status.analysis_fps, 0)}</span>&nbsp;güncelleme/sn
      </summary>
      <div className="card absolute right-0 top-11 z-30 w-72 p-5 text-[14px]">
        <p className="font-semibold">Performans</p>
        <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5">
          <dt className="text-chalk-2">İfade güncellemesi</dt>
          <dd className="numeric">{num(status.analysis_fps, 1)}/sn</dd>
          {status.detect_fps != null && (
            <>
              <dt className="text-chalk-2">Kişi tespiti</dt>
              <dd className="numeric">{num(status.detect_fps, 1)}/sn</dd>
            </>
          )}
          <dt className="text-chalk-2">Kamera</dt>
          <dd className="numeric">{num(status.source.fps, 0)} kare/sn</dd>
        </dl>
        {Object.keys(t).length > 0 && (
          <dl className="mt-4 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 border-t border-line pt-4">
            {STAGES.filter(([k]) => t[k] != null).map(([k, label]) => (
              <div key={k} className="contents">
                <dt className="text-chalk-2">{label}</dt>
                <dd className="numeric">{num(t[k])} ms</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </details>
  )
}

const MODEL_ORDER = ['detector', 'face', 'emotion', 'engagement'] as const

function Models({ status }: { status: EngineStatus }) {
  return (
    <section className="card p-6 sm:p-8" aria-labelledby="models-title">
      <h2 id="models-title" className="display text-xl font-semibold">
        Modeller
      </h2>
      <p className="mt-1 text-[15px] text-chalk-3">
        {status.mode === 'mock' ? 'Demo modunda model çıktıları simüle edilir.' : 'Her göstergenin dayandığı öğrenilmiş model'}
      </p>
      <ul className="mt-5 divide-y divide-line">
        {MODEL_ORDER.map((k) => {
          const m = status.models[k]
          if (!m) return null
          return (
            <li key={k} className="grid grid-cols-[1fr_auto] gap-x-4 py-3.5 text-[15px]">
              <span className="font-medium text-chalk">{m.task}</span>
              <span
                className={clsx(
                  'text-[14px]',
                  m.simulated ? 'text-chalk-3' : m.loaded ? 'text-[var(--tone-positive)]' : 'text-[var(--tone-tired)]',
                )}
              >
                {m.simulated ? 'Simüle' : m.loaded ? 'Çalışıyor' : 'Yüklü değil'}
              </span>
              <span className="col-span-2 mt-0.5 text-[14px] text-chalk-3">
                {m.name}, {m.data}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

