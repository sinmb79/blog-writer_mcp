import React, { useState, useEffect, useCallback } from 'react'
import { Loader2, RefreshCw, Search, Filter } from 'lucide-react'

const LEVEL_STYLES = {
  ERROR: 'text-error',
  CRITICAL: 'text-error font-semibold',
  WARNING: 'text-warning',
  INFO: 'text-info',
  DEBUG: 'text-subtext',
}

const FILTERS = [
  { value: '', label: '전체' },
  { value: 'scheduler', label: '스케줄러' },
  { value: 'collector', label: '수집' },
  { value: 'writer', label: '글쓰기' },
  { value: 'converter', label: '변환' },
  { value: 'publisher', label: '발행' },
  { value: 'novel', label: '소설' },
  { value: 'analytics', label: '분석' },
  { value: 'error', label: '에러만' },
]

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterModule, setFilterModule] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [total, setTotal] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(false)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterModule) params.set('filter', filterModule)
      if (search) params.set('search', search)
      params.set('limit', '200')

      const res = await fetch(`/api/logs?${params}`)
      const data = await res.json()
      setLogs(data.logs || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('Logs 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }, [filterModule, search])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(fetchLogs, 5000)
    return () => clearInterval(timer)
  }, [autoRefresh, fetchLogs])

  const handleSearch = (e) => {
    e.preventDefault()
    setSearch(searchInput)
  }

  const levelCount = (level) => logs.filter(l => l.level === level).length

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">시스템 로그</h1>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-subtext cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="accent-accent"
            />
            자동 새로고침 (5초)
          </label>
          <button
            onClick={fetchLogs}
            className="text-xs text-subtext hover:text-accent flex items-center gap-1 border border-border px-2 py-1 rounded"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            새로고침
          </button>
        </div>
      </div>

      {/* 필터 + 검색 */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* 모듈 필터 드롭다운 */}
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-subtext flex-shrink-0" />
          <div className="flex flex-wrap gap-1">
            {FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => setFilterModule(f.value)}
                className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
                  filterModule === f.value
                    ? 'bg-accent text-bg font-semibold'
                    : 'border border-border text-subtext hover:text-text'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* 검색 */}
        <form onSubmit={handleSearch} className="flex gap-2 ml-auto">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-subtext" />
            <input
              type="text"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="메시지 검색..."
              className="bg-bg border border-border rounded pl-7 pr-3 py-1.5 text-xs text-text placeholder-subtext focus:outline-none focus:border-accent w-48"
            />
          </div>
          <button type="submit" className="text-xs bg-accent text-bg px-3 py-1.5 rounded font-semibold hover:opacity-80">
            검색
          </button>
          {search && (
            <button
              type="button"
              onClick={() => { setSearch(''); setSearchInput('') }}
              className="text-xs text-subtext hover:text-text"
            >
              초기화
            </button>
          )}
        </form>
      </div>

      {/* 통계 바 */}
      <div className="flex gap-4 text-xs">
        <span className="text-subtext">총 {total}건</span>
        {levelCount('ERROR') > 0 && <span className="text-error">오류 {levelCount('ERROR')}건</span>}
        {levelCount('WARNING') > 0 && <span className="text-warning">경고 {levelCount('WARNING')}건</span>}
        {levelCount('INFO') > 0 && <span className="text-info">정보 {levelCount('INFO')}건</span>}
      </div>

      {/* 로그 리스트 */}
      <div className="card overflow-hidden">
        {loading && logs.length === 0 ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-accent" size={24} />
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-12 text-subtext text-sm">
            로그가 없습니다.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-full">
              {/* 테이블 헤더 */}
              <div className="flex gap-3 px-3 py-2 border-b border-border text-xs text-subtext bg-bg/50 sticky top-0">
                <span className="w-36 flex-shrink-0">시각</span>
                <span className="w-16 flex-shrink-0">레벨</span>
                <span className="w-24 flex-shrink-0">모듈</span>
                <span className="flex-1">메시지</span>
              </div>

              {/* 로그 행 */}
              <div className="max-h-[calc(100vh-320px)] overflow-y-auto">
                {logs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`flex gap-3 px-3 py-1.5 border-b border-border/30 hover:bg-card-hover text-xs font-mono ${
                      idx % 2 === 0 ? '' : 'bg-black/10'
                    }`}
                  >
                    <span className="w-36 flex-shrink-0 text-subtext whitespace-nowrap">
                      {log.time}
                    </span>
                    <span className={`w-16 flex-shrink-0 ${LEVEL_STYLES[log.level] || 'text-subtext'}`}>
                      {log.level}
                    </span>
                    <span className="w-24 flex-shrink-0 text-subtext truncate">
                      [{log.module}]
                    </span>
                    <span className="flex-1 text-text break-all">
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
