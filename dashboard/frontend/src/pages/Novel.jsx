import React, { useState, useEffect } from 'react'
import { Loader2, RefreshCw, Plus, X, Play, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'

function ProgressBar({ value, max }) {
  const pct = max > 0 ? Math.min(100, Math.round(value / max * 100)) : 0
  const color = pct >= 80 ? '#3a7d5c' : pct >= 40 ? '#c8a84e' : '#4a5abf'
  return (
    <div>
      <div className="flex justify-between text-xs text-subtext mb-1">
        <span>{value} / {max} 화</span>
        <span style={{ color }}>{pct}%</span>
      </div>
      <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
        <div style={{ width: `${pct}%`, background: color }} className="h-full rounded-full transition-all" />
      </div>
    </div>
  )
}

function NewNovelModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    novel_id: '',
    title: '',
    title_ko: '',
    genre: '',
    setting: '',
    characters: '',
    base_story: '',
    publish_schedule: '매주 월/목 09:00',
    episode_count_target: 50,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/novels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, episode_count_target: Number(form.episode_count_target) }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '생성 실패')
      }
      const data = await res.json()
      onCreated(data)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const field = (name, label, placeholder = '', type = 'text', rows = 0) => (
    <div>
      <label className="block text-xs text-subtext mb-1">{label}</label>
      {rows > 0 ? (
        <textarea
          rows={rows}
          value={form[name]}
          onChange={e => setForm(f => ({ ...f, [name]: e.target.value }))}
          placeholder={placeholder}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text placeholder-subtext focus:outline-none focus:border-accent resize-none"
          required
        />
      ) : (
        <input
          type={type}
          value={form[name]}
          onChange={e => setForm(f => ({ ...f, [name]: e.target.value }))}
          placeholder={placeholder}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text placeholder-subtext focus:outline-none focus:border-accent"
          required
        />
      )}
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 overflow-y-auto py-6" onClick={onClose}>
      <div className="card w-full max-w-lg mx-4 p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-accent flex items-center gap-2">
            <Plus size={16} />
            새 소설 만들기
          </h3>
          <button onClick={onClose} className="text-subtext hover:text-text"><X size={18} /></button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {field('novel_id', '소설 ID (영문)', 'shadow-protocol')}
            {field('genre', '장르', '판타지 / SF / 로맨스')}
          </div>
          {field('title', '영문 제목', 'Shadow Protocol')}
          {field('title_ko', '한국어 제목', '그림자 프로토콜')}
          {field('setting', '세계관 설정', '2050년 서울, AI와 인간이 공존하는 사회...', 'text', 3)}
          {field('characters', '주요 등장인물', '주인공: 김하준(29세, AI 보안 전문가)...', 'text', 3)}
          {field('base_story', '기본 스토리', '주인공이 우연히 금지된 AI를 발견하면서...', 'text', 4)}
          <div className="grid grid-cols-2 gap-3">
            {field('publish_schedule', '발행 일정', '매주 월/목 09:00')}
            {field('episode_count_target', '목표 에피소드', '50', 'number')}
          </div>

          {error && <p className="text-error text-xs">{error}</p>}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 border border-border text-sm rounded hover:border-accent/50 transition-colors">
              취소
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2 bg-accent text-bg text-sm font-semibold rounded hover:opacity-80 transition-opacity disabled:opacity-50"
            >
              {loading ? <Loader2 size={14} className="animate-spin inline" /> : '소설 생성'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function NovelCard({ novel, onGenerate }) {
  const [expanded, setExpanded] = useState(false)
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    if (!confirm(`"${novel.title_ko}" 다음 에피소드를 생성할까요? 수 분이 걸릴 수 있습니다.`)) return
    setGenerating(true)
    try {
      const res = await fetch(`/api/novels/${novel.novel_id}/generate`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        alert(`에피소드 ${data.episode_num}화 생성 완료!`)
        onGenerate()
      } else {
        alert('생성 실패: ' + (data.detail || '알 수 없는 오류'))
      }
    } catch (e) {
      alert('생성 실패: ' + e.message)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-text">{novel.title_ko}</h3>
          <div className="flex gap-2 mt-1">
            <span className="tag bg-info/10 text-info">{novel.genre}</span>
            <span className={`tag ${novel.status === 'active' ? 'badge-done' : 'badge-waiting'}`}>
              {novel.status === 'active' ? '연재중' : '중단'}
            </span>
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-1.5 text-xs bg-accent text-bg px-3 py-1.5 rounded font-semibold hover:opacity-80 transition-opacity disabled:opacity-50"
        >
          {generating ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          다음 회 생성
        </button>
      </div>

      <ProgressBar value={novel.current_episode || 0} max={novel.episode_count_target || 50} />

      {novel.publish_schedule && (
        <p className="text-xs text-subtext mt-2">연재 일정: {novel.publish_schedule}</p>
      )}

      {/* 에피소드 테이블 토글 */}
      {(novel.episodes?.length > 0) && (
        <div className="mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-subtext hover:text-accent transition-colors"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            에피소드 목록 ({novel.episodes.length}회)
          </button>

          {expanded && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-subtext border-b border-border">
                    <th className="text-left py-1.5">화수</th>
                    <th className="text-left py-1.5">제목</th>
                    <th className="text-right py-1.5">생성일</th>
                    <th className="text-right py-1.5">분량</th>
                  </tr>
                </thead>
                <tbody>
                  {novel.episodes.map((ep, idx) => (
                    <tr key={idx} className="border-b border-border/50 hover:bg-card-hover">
                      <td className="py-1.5 text-accent font-mono">{ep.episode_num}화</td>
                      <td className="py-1.5 max-w-[200px] truncate">{ep.title}</td>
                      <td className="py-1.5 text-right text-subtext">{ep.generated_at}</td>
                      <td className="py-1.5 text-right text-subtext">{ep.word_count?.toLocaleString()}자</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Novel() {
  const [novels, setNovels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)

  const fetchNovels = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/novels')
      const data = await res.json()
      setNovels(data.novels || [])
    } catch (e) {
      console.error('Novel 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchNovels() }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold flex items-center gap-2">
          <BookOpen size={20} className="text-accent" />
          소설 연재 관리
        </h1>
        <div className="flex gap-2">
          <button
            onClick={fetchNovels}
            className="text-xs text-subtext hover:text-accent border border-border px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw size={12} />
            새로고침
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 text-xs bg-accent text-bg font-semibold px-3 py-1.5 rounded hover:opacity-80 transition-opacity"
          >
            <Plus size={13} />
            새 소설 만들기
          </button>
        </div>
      </div>

      {novels.length === 0 ? (
        <div className="card p-8 text-center">
          <BookOpen size={40} className="text-subtext mx-auto mb-3" />
          <p className="text-subtext text-sm mb-3">등록된 소설이 없습니다.</p>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-1.5 text-sm bg-accent text-bg font-semibold px-4 py-2 rounded hover:opacity-80 transition-opacity"
          >
            <Plus size={14} />
            첫 소설 만들기
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {novels.map(novel => (
            <NovelCard key={novel.novel_id} novel={novel} onGenerate={fetchNovels} />
          ))}
        </div>
      )}

      {showModal && (
        <NewNovelModal
          onClose={() => setShowModal(false)}
          onCreated={() => fetchNovels()}
        />
      )}
    </div>
  )
}
