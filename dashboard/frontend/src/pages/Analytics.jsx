import React, { useState, useEffect } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { Loader2, RefreshCw, Users, Eye, Clock, MousePointerClick } from 'lucide-react'

const PERIOD_DAYS = { '이번주': 7, '이번달': 30, '전체': 365 }
const PLATFORM_COLORS = { blogger: '#c8a84e', youtube: '#bf3a3a', instagram: '#4a5abf', x: '#888880' }

function KpiCard({ label, value, icon: Icon, color }) {
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg bg-border ${color}`}>
        <Icon size={18} />
      </div>
      <div>
        <div className="text-xs text-subtext">{label}</div>
        <div className="text-xl font-bold text-text">{value}</div>
      </div>
    </div>
  )
}

function formatSec(sec) {
  if (!sec) return '0분'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}분 ${s}초` : `${s}초`
}

export default function Analytics() {
  const [period, setPeriod] = useState('이번주')
  const [analytics, setAnalytics] = useState(null)
  const [chart, setChart] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const days = PERIOD_DAYS[period]
      const [aRes, cRes] = await Promise.all([
        fetch('/api/analytics'),
        fetch(`/api/analytics/chart?days=${days}`),
      ])
      const a = await aRes.json()
      const c = await cRes.json()
      setAnalytics(a)
      setChart(c.chart || [])
    } catch (e) {
      console.error('Analytics 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [period])

  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    )
  }

  const kpi = analytics?.kpi || {}
  const corners = analytics?.corners || []
  const topPosts = analytics?.top_posts || []
  const platforms = analytics?.platforms || []

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">성과 분석</h1>
        <div className="flex items-center gap-2">
          {/* 기간 선택 */}
          <div className="flex rounded border border-border overflow-hidden">
            {Object.keys(PERIOD_DAYS).map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 text-xs transition-colors ${
                  period === p
                    ? 'bg-accent text-bg font-semibold'
                    : 'text-subtext hover:text-text'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            className="text-xs text-subtext hover:text-accent"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* KPI 카드 4개 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="방문자" value={kpi.visitors?.toLocaleString() || '0'} icon={Users} color="text-accent" />
        <KpiCard label="페이지뷰" value={kpi.pageviews?.toLocaleString() || '0'} icon={Eye} color="text-info" />
        <KpiCard label="평균 체류시간" value={formatSec(kpi.avg_duration_sec)} icon={Clock} color="text-success" />
        <KpiCard label="CTR" value={`${kpi.ctr || 0}%`} icon={MousePointerClick} color="text-warning" />
      </div>

      {/* 방문자 라인차트 */}
      <div className="card p-4">
        <h2 className="text-sm font-semibold text-accent mb-4">방문자 추이 ({period})</h2>
        {chart.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-subtext text-sm">
            데이터 없음
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chart} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#222228" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#888880', fontSize: 11 }}
                tickFormatter={d => d.slice(5)}
              />
              <YAxis tick={{ fill: '#888880', fontSize: 11 }} width={40} />
              <Tooltip
                contentStyle={{ background: '#111116', border: '1px solid #222228', borderRadius: 6 }}
                labelStyle={{ color: '#e0e0d8' }}
              />
              <Line
                type="monotone"
                dataKey="visitors"
                name="방문자"
                stroke="#c8a84e"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="pageviews"
                name="페이지뷰"
                stroke="#3a7d5c"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 코너별 성과 테이블 */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-accent mb-3">코너별 성과</h2>
          {corners.length === 0 ? (
            <p className="text-subtext text-sm">데이터 없음</p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-subtext border-b border-border">
                  <th className="text-left py-2">코너</th>
                  <th className="text-right py-2">방문자</th>
                  <th className="text-right py-2">페이지뷰</th>
                  <th className="text-right py-2">글 수</th>
                </tr>
              </thead>
              <tbody>
                {corners.map((c, idx) => (
                  <tr key={idx} className="border-b border-border/50 hover:bg-card-hover">
                    <td className="py-2">{c.corner}</td>
                    <td className="py-2 text-right text-accent">{c.visitors.toLocaleString()}</td>
                    <td className="py-2 text-right">{c.pageviews.toLocaleString()}</td>
                    <td className="py-2 text-right text-subtext">{c.posts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 인기글 TOP 5 */}
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-accent mb-3">인기글 TOP 5</h2>
          {topPosts.length === 0 ? (
            <p className="text-subtext text-sm">데이터 없음</p>
          ) : (
            <div className="space-y-2">
              {topPosts.map((post, idx) => (
                <div key={idx} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
                  <span className="text-accent font-bold text-sm w-5 flex-shrink-0">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text truncate">{post.title}</p>
                    <div className="flex gap-3 mt-0.5">
                      <span className="text-xs text-subtext">{post.corner}</span>
                      <span className="text-xs text-accent">{post.visitors?.toLocaleString()} 방문</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 플랫폼별 성과 */}
      {platforms.length > 0 && (
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-accent mb-4">플랫폼별 성과</h2>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={platforms} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#222228" />
              <XAxis dataKey="platform" tick={{ fill: '#888880', fontSize: 12 }} />
              <YAxis tick={{ fill: '#888880', fontSize: 11 }} width={40} />
              <Tooltip
                contentStyle={{ background: '#111116', border: '1px solid #222228', borderRadius: 6 }}
                labelStyle={{ color: '#e0e0d8' }}
              />
              <Bar dataKey="visitors" name="방문자" radius={[4, 4, 0, 0]}>
                {platforms.map((p, idx) => (
                  <Cell key={idx} fill={PLATFORM_COLORS[p.platform] || '#4a5abf'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
