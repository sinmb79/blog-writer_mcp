import React, { useState, useEffect } from 'react'
import { Loader2, RefreshCw, AlertTriangle, DollarSign, Cpu } from 'lucide-react'

export default function CostMonitor() {
  const [subscriptions, setSubscriptions] = useState([])
  const [usage, setUsage] = useState([])
  const [totalMonthly, setTotalMonthly] = useState(0)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [sRes, uRes] = await Promise.all([
        fetch('/api/cost/subscriptions'),
        fetch('/api/cost/usage'),
      ])
      const sData = await sRes.json()
      const uData = await uRes.json()
      setSubscriptions(sData.subscriptions || [])
      setTotalMonthly(sData.total_monthly_usd || 0)
      setUsage(uData.usage || [])
    } catch (e) {
      console.error('Cost 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  if (loading) {
    return <div className="flex justify-center py-8"><Loader2 className="animate-spin text-accent" size={24} /></div>
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-accent flex items-center gap-2">
          <DollarSign size={14} />
          비용 모니터링
        </h3>
        <button onClick={fetchData} className="text-xs text-subtext hover:text-accent flex items-center gap-1">
          <RefreshCw size={12} />
          새로고침
        </button>
      </div>

      {/* 월간 비용 요약 */}
      <div className="card p-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-subtext">예상 월간 고정 비용</p>
          <p className="text-2xl font-bold text-accent">${totalMonthly.toFixed(2)}</p>
        </div>
        <DollarSign size={32} className="text-accent/30" />
      </div>

      {/* 구독 테이블 */}
      <div className="card p-4">
        <h4 className="text-sm font-medium text-text mb-3">구독 현황</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-subtext border-b border-border">
                <th className="text-left py-2">서비스</th>
                <th className="text-left py-2">제공사</th>
                <th className="text-center py-2">상태</th>
                <th className="text-right py-2">월 비용</th>
                <th className="text-right py-2">갱신 D-Day</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.map(sub => (
                <tr key={sub.id} className="border-b border-border/50 hover:bg-card-hover">
                  <td className="py-2 font-medium">{sub.name}</td>
                  <td className="py-2 text-subtext">{sub.provider}</td>
                  <td className="py-2 text-center">
                    <span className={`tag ${sub.active ? 'badge-done' : 'badge-waiting'}`}>
                      {sub.active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="py-2 text-right">
                    {sub.monthly_cost_usd > 0 ? `$${sub.monthly_cost_usd.toFixed(2)}` : '종량제'}
                  </td>
                  <td className="py-2 text-right">
                    {sub.days_until_renewal != null ? (
                      <span className={sub.alert ? 'text-error font-semibold' : 'text-subtext'}>
                        {sub.alert && <AlertTriangle size={10} className="inline mr-0.5" />}
                        D-{sub.days_until_renewal}
                      </span>
                    ) : (
                      <span className="text-subtext">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* API 사용량 */}
      <div className="card p-4">
        <h4 className="text-sm font-medium text-text mb-3 flex items-center gap-2">
          <Cpu size={13} />
          API 사용량 (로그 기반 추정)
        </h4>
        {usage.length === 0 ? (
          <p className="text-subtext text-sm">사용량 데이터 없음 (로그에서 파싱)</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-subtext border-b border-border">
                <th className="text-left py-2">제공사</th>
                <th className="text-right py-2">토큰 수</th>
                <th className="text-right py-2">예상 비용</th>
              </tr>
            </thead>
            <tbody>
              {usage.map((u, idx) => (
                <tr key={idx} className="border-b border-border/50">
                  <td className="py-2 font-medium capitalize">{u.provider}</td>
                  <td className="py-2 text-right font-mono">{u.tokens.toLocaleString()}</td>
                  <td className="py-2 text-right text-accent">${u.estimated_cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="text-xs text-subtext mt-2">* 사용량은 로그 파싱 기반 근사치입니다.</p>
      </div>
    </div>
  )
}
