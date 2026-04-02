import React, { useState, useEffect } from 'react'
import { Loader2, CheckCircle2, XCircle, RefreshCw, X, Star, ExternalLink } from 'lucide-react'

const STATUS_COLORS = {
  queue: 'bg-info/10 text-info border-info/30',
  writing: 'bg-warning/10 text-warning border-warning/30',
  review: 'bg-accent/10 text-accent border-accent/30',
  published: 'bg-success/10 text-success border-success/30',
}

const STATUS_BADGE = {
  queue: 'badge-waiting',
  writing: 'badge-running',
  review: 'badge-running',
  published: 'badge-done',
}

function QualityBar({ score }) {
  if (!score) return null
  const color = score >= 80 ? '#3a7d5c' : score >= 60 ? '#c8a84e' : '#bf3a3a'
  return (
    <div className="flex items-center gap-1.5 mt-1">
      <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
        <div style={{ width: `${score}%`, background: color }} className="h-full rounded-full" />
      </div>
      <span className="text-xs font-mono" style={{ color }}>{score}</span>
    </div>
  )
}

function CardModal({ card, onClose, onApprove, onReject }) {
  if (!card) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="card w-full max-w-lg mx-4 p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="font-semibold text-text mb-1">{card.title}</h3>
            <div className="flex gap-2">
              {card.corner && (
                <span className="tag bg-accent/10 text-accent border border-accent/20">{card.corner}</span>
              )}
              <span className={`tag ${STATUS_BADGE[card.status]}`}>{card.status}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-subtext hover:text-text">
            <X size={18} />
          </button>
        </div>

        {card.quality_score > 0 && (
          <div className="mb-3">
            <div className="flex items-center gap-1 text-xs text-subtext mb-1">
              <Star size={11} />
              품질 점수
            </div>
            <QualityBar score={card.quality_score} />
          </div>
        )}

        {card.source && (
          <div className="mb-3">
            <p className="text-xs text-subtext mb-1">출처</p>
            <p className="text-xs text-info break-all">{card.source}</p>
          </div>
        )}

        {card.summary && (
          <div className="mb-4">
            <p className="text-xs text-subtext mb-1">내용 요약</p>
            <p className="text-sm text-text leading-relaxed line-clamp-4">{card.summary}</p>
          </div>
        )}

        {card.created_at && (
          <p className="text-xs text-subtext mb-4">생성일: {card.created_at?.slice(0, 16)}</p>
        )}

        {card.status === 'review' && (
          <div className="flex gap-2">
            <button
              onClick={() => onApprove(card.id)}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-success text-white text-sm font-medium rounded hover:opacity-80 transition-opacity"
            >
              <CheckCircle2 size={14} />
              승인
            </button>
            <button
              onClick={() => onReject(card.id)}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-error text-white text-sm font-medium rounded hover:opacity-80 transition-opacity"
            >
              <XCircle size={14} />
              거부
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function KanbanCard({ card, onClick }) {
  return (
    <div
      className="card p-3 cursor-pointer hover:border-accent/50 transition-colors mb-2"
      onClick={() => onClick(card)}
    >
      <p className="text-sm font-medium text-text line-clamp-2 mb-1">{card.title}</p>
      {card.corner && (
        <span className="tag bg-accent/10 text-accent text-xs">{card.corner}</span>
      )}
      <QualityBar score={card.quality_score} />
      {card.status === 'review' && (
        <div className="flex gap-1 mt-2" onClick={e => e.stopPropagation()}>
          <button
            onClick={async () => {
              await fetch(`/api/content/${card.id}/approve`, { method: 'POST' })
              window.location.reload()
            }}
            className="flex-1 text-xs py-1 bg-success/20 text-success rounded hover:bg-success/30 transition-colors"
          >
            승인
          </button>
          <button
            onClick={async () => {
              await fetch(`/api/content/${card.id}/reject`, { method: 'POST' })
              window.location.reload()
            }}
            className="flex-1 text-xs py-1 bg-error/20 text-error rounded hover:bg-error/30 transition-colors"
          >
            거부
          </button>
        </div>
      )}
    </div>
  )
}

export default function Content() {
  const [columns, setColumns] = useState({})
  const [loading, setLoading] = useState(true)
  const [selectedCard, setSelectedCard] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  const fetchContent = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/content')
      const data = await res.json()
      setColumns(data.columns || {})
    } catch (e) {
      console.error('Content 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchContent() }, [])

  const handleApprove = async (id) => {
    setActionLoading(true)
    try {
      await fetch(`/api/content/${id}/approve`, { method: 'POST' })
      setSelectedCard(null)
      await fetchContent()
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (id) => {
    setActionLoading(true)
    try {
      await fetch(`/api/content/${id}/reject`, { method: 'POST' })
      setSelectedCard(null)
      await fetchContent()
    } finally {
      setActionLoading(false)
    }
  }

  const handleManualWrite = async () => {
    if (!confirm('수집 + 글쓰기 봇을 수동으로 실행할까요? 수 분이 걸릴 수 있습니다.')) return
    try {
      const res = await fetch('/api/manual-write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      const msg = data.results?.map(r => `${r.step}: ${r.success ? '성공' : r.error || '실패'}`).join('\n')
      alert(msg || '실행 완료')
      await fetchContent()
    } catch (e) {
      alert('실행 실패: ' + e.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    )
  }

  const colOrder = ['queue', 'writing', 'review', 'published']

  return (
    <div className="p-4 md:p-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-bold">콘텐츠 관리</h1>
        <div className="flex gap-2">
          <button
            onClick={fetchContent}
            className="flex items-center gap-1.5 text-xs text-subtext hover:text-accent border border-border px-3 py-1.5 rounded transition-colors"
          >
            <RefreshCw size={12} />
            새로고침
          </button>
          <button
            onClick={handleManualWrite}
            className="flex items-center gap-1.5 text-xs bg-accent text-bg font-semibold px-3 py-1.5 rounded hover:opacity-80 transition-opacity"
          >
            수동 글쓰기 실행
          </button>
        </div>
      </div>

      {/* 칸반 보드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {colOrder.map(colId => {
          const col = columns[colId]
          if (!col) return null
          const cards = col.cards || []
          return (
            <div key={colId} className="bg-card/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-accent">{col.label}</h3>
                <span className="text-xs bg-border text-subtext px-2 py-0.5 rounded-full">
                  {cards.length}
                </span>
              </div>
              <div className="kanban-col overflow-y-auto max-h-[60vh]">
                {cards.length === 0 ? (
                  <p className="text-xs text-subtext text-center py-8">비어있음</p>
                ) : (
                  cards.map(card => (
                    <KanbanCard key={card.id} card={card} onClick={setSelectedCard} />
                  ))
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* 카드 상세 모달 */}
      {selectedCard && (
        <CardModal
          card={selectedCard}
          onClose={() => setSelectedCard(null)}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
    </div>
  )
}
