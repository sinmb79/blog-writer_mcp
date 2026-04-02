import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { RefreshCw, CheckCircle2, Loader2, Clock, XCircle, AlertCircle, Zap, CalendarDays } from 'lucide-react'

const STEP_ICONS = {
  done: <CheckCircle2 size={16} className="text-success" />,
  running: <Loader2 size={16} className="text-info animate-spin" />,
  waiting: <Clock size={16} className="text-subtext" />,
  error: <XCircle size={16} className="text-error" />,
}

const STEP_LABELS = {
  done: '완료',
  running: '실행중',
  waiting: '대기',
  error: '오류',
}

const CORNER_COLORS = ['#c8a84e', '#3a7d5c', '#4a5abf', '#bf3a3a', '#7a5abf', '#5a7abf']

function KpiCard({ label, value, sub, color }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-subtext mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color || 'text-text'}`}>{value}</div>
      {sub && <div className="text-xs text-subtext mt-1">{sub}</div>}
    </div>
  )
}

function PipelineStep({ name, status, done_at }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <div className="flex items-center gap-2">
        {STEP_ICONS[status] || STEP_ICONS.waiting}
        <span className="text-sm">{name}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`tag ${
          status === 'done' ? 'badge-done' :
          status === 'running' ? 'badge-running' :
          status === 'error' ? 'badge-error' :
          'badge-waiting'
        }`}>
          {STEP_LABELS[status] || '대기'}
        </span>
        {done_at && <span className="text-xs text-subtext font-mono">{done_at}</span>}
      </div>
    </div>
  )
}

const LOG_LEVEL_COLORS = {
  ERROR: 'text-error',
  WARNING: 'text-warning',
  INFO: 'text-info',
  DEBUG: 'text-subtext',
}

export default function Overview() {
  const [kpi, setKpi] = useState(null)
  const [pipeline, setPipeline] = useState([])
  const [activity, setActivity] = useState([])
  const [corners, setCorners] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState('')

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [ovRes, pipRes, actRes] = await Promise.all([
        fetch('/api/overview'),
        fetch('/api/pipeline'),
        fetch('/api/activity'),
      ])
      const ov = await ovRes.json()
      const pip = await pipRes.json()
      const act = await actRes.json()

      setKpi(ov.kpi)
      setCorners(ov.corner_ratio || [])
      setPipeline(pip.steps || [])
      setActivity(act.logs || [])
      setLastUpdated(new Date().toLocaleTimeString('ko-KR'))
    } catch (e) {
      console.error('Overview 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    const timer = setInterval(fetchAll, 60000)
    return () => clearInterval(timer)
  }, [])

  if (loading && !kpi) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    )
  }

  const revenue = kpi?.revenue || {}

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-text">개요 대시보드</h1>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-subtext">업데이트: {lastUpdated}</span>
          )}
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 text-xs text-subtext hover:text-accent transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            새로고침
          </button>
        </div>
      </div>

      {/* KPI 카드 4개 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="오늘 발행"
          value={kpi?.today ?? 0}
          sub="블로그+SNS"
          color={kpi?.today > 0 ? 'text-success' : 'text-subtext'}
        />
        <KpiCard
          label="이번주 발행"
          value={kpi?.this_week ?? 0}
          sub="7일 기준"
          color="text-accent"
        />
        <KpiCard
          label="총 글 수"
          value={kpi?.total ?? 0}
          sub={kpi?.today > 0 ? `+${kpi.today} 오늘` : '누적'}
          color="text-text"
        />
        <KpiCard
          label="수익"
          value={revenue.amount != null ? `$${revenue.amount.toFixed(2)}` : '$0.00'}
          sub={revenue.status || '대기중'}
          color={revenue.amount > 0 ? 'text-success' : 'text-subtext'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 파이프라인 상태 */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-accent mb-3">파이프라인 상태</h2>
          {pipeline.length === 0 ? (
            <p className="text-subtext text-sm">로그 데이터 없음</p>
          ) : (
            pipeline.map(step => (
              <PipelineStep key={step.id} {...step} />
            ))
          )}
        </div>

        {/* 코너별 발행 비율 */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-accent mb-3">코너별 발행 비율</h2>
          {corners.length === 0 ? (
            <p className="text-subtext text-sm">발행 데이터 없음</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={corners} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: '#888880', fontSize: 12 }}
                  width={70}
                />
                <Tooltip
                  contentStyle={{ background: '#111116', border: '1px solid #222228', borderRadius: 6 }}
                  labelStyle={{ color: '#e0e0d8' }}
                  formatter={(v, n, p) => [`${p.payload.count}건 (${v}%)`, '비율']}
                />
                <Bar dataKey="ratio" radius={[0, 4, 4, 0]}>
                  {corners.map((_, idx) => (
                    <Cell key={idx} fill={CORNER_COLORS[idx % CORNER_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 빠른 액션 */}
      <div className="card p-4">
        <h2 className="text-sm font-semibold text-accent mb-3">빠른 액션</h2>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => window.location.href = '#content'}
            className="flex items-center gap-1.5 px-3 py-2 bg-accent text-bg text-xs font-semibold rounded hover:opacity-80 transition-opacity"
          >
            <AlertCircle size={13} />
            승인 대기 확인
          </button>
          <button
            onClick={async () => {
              const r = await fetch('/api/manual-write', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
              const d = await r.json()
              alert(JSON.stringify(d.results?.map(x => `${x.step}: ${x.success ? '성공' : x.error}`), null, 2))
            }}
            className="flex items-center gap-1.5 px-3 py-2 border border-border text-xs rounded hover:border-accent hover:text-accent transition-colors"
          >
            <Zap size={13} />
            오늘 글감 수동 실행
          </button>
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 px-3 py-2 border border-border text-xs rounded hover:border-accent hover:text-accent transition-colors"
          >
            <CalendarDays size={13} />
            데이터 새로고침
          </button>
        </div>
      </div>

      {/* 최근 활동 로그 */}
      <div className="card p-4">
        <h2 className="text-sm font-semibold text-accent mb-3">최근 활동</h2>
        {activity.length === 0 ? (
          <p className="text-subtext text-sm">로그 없음</p>
        ) : (
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {activity.map((log, idx) => (
              <div key={idx} className="flex gap-3 text-xs py-1 border-b border-border last:border-0">
                <span className="text-subtext font-mono whitespace-nowrap">{log.time}</span>
                <span className={`font-mono ${LOG_LEVEL_COLORS[log.level] || 'text-subtext'} w-12 flex-shrink-0`}>
                  {log.level}
                </span>
                <span className="text-subtext w-20 flex-shrink-0">[{log.module}]</span>
                <span className="text-text truncate">{log.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
