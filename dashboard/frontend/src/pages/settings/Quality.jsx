import React, { useState, useEffect } from 'react'
import { Loader2, Save, Shield } from 'lucide-react'

function Slider({ label, value, min, max, onChange, help }) {
  const pct = ((value - min) / (max - min)) * 100
  const color = value >= 80 ? '#3a7d5c' : value >= 60 ? '#c8a84e' : '#bf3a3a'
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm text-text">{label}</label>
        <span className="text-sm font-bold font-mono" style={{ color }}>{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-accent"
        style={{ accentColor: color }}
      />
      <div className="flex justify-between text-xs text-subtext">
        <span>{min}</span>
        {help && <span>{help}</span>}
        <span>{max}</span>
      </div>
    </div>
  )
}

export default function Quality() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(d => setSettings(d))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const updateQuality = (key, value) => {
    setSettings(s => ({
      ...s,
      quality_gates: { ...s.quality_gates, [key]: value },
    }))
  }

  const updateSchedule = (key, value) => {
    setSettings(s => ({
      ...s,
      schedule: { ...s.schedule, [key]: value },
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: settings }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      alert('저장 실패: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center py-8"><Loader2 className="animate-spin text-accent" size={24} /></div>
  }

  const qg = settings?.quality_gates || {}

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-accent flex items-center gap-2">
        <Shield size={14} />
        품질 기준 설정
      </h3>

      {/* 품질 점수 슬라이더 */}
      <div className="card p-4">
        <h4 className="text-sm font-medium text-text mb-4">품질 게이트 점수</h4>
        <Slider
          label="Gate 1 — 수집 최소 점수"
          value={qg.gate1_research_min_score ?? 60}
          min={0} max={100}
          help="리서치 품질"
          onChange={v => updateQuality('gate1_research_min_score', v)}
        />
        <Slider
          label="Gate 2 — 글쓰기 최소 점수"
          value={qg.gate2_writing_min_score ?? 70}
          min={0} max={100}
          help="글 품질"
          onChange={v => updateQuality('gate2_writing_min_score', v)}
        />
        <Slider
          label="Gate 3 — 자동 승인 점수"
          value={qg.gate3_auto_approve_score ?? 90}
          min={0} max={100}
          help="이 이상이면 자동 승인"
          onChange={v => updateQuality('gate3_auto_approve_score', v)}
        />
        <Slider
          label="최소 핵심 포인트 수"
          value={qg.min_key_points ?? 2}
          min={1} max={10}
          onChange={v => updateQuality('min_key_points', v)}
        />
        <Slider
          label="최소 단어 수"
          value={qg.min_word_count ?? 300}
          min={100} max={2000}
          onChange={v => updateQuality('min_word_count', v)}
        />

        {/* 크로스 리뷰 / 안전 검사 */}
        <div className="mt-4 space-y-3 border-t border-border pt-4">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm text-text">Gate 3 검수 필요</span>
            <div
              className={`relative w-12 h-6 rounded-full transition-colors ${qg.gate3_review_required ? 'bg-success' : 'bg-border'}`}
              onClick={() => updateQuality('gate3_review_required', !qg.gate3_review_required)}
            >
              <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${qg.gate3_review_required ? 'translate-x-7' : 'translate-x-1'}`} />
            </div>
          </label>
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm text-text">안전 검사 (Safety Check)</span>
            <div
              className={`relative w-12 h-6 rounded-full transition-colors ${qg.safety_check ? 'bg-success' : 'bg-border'}`}
              onClick={() => updateQuality('safety_check', !qg.safety_check)}
            >
              <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${qg.safety_check ? 'translate-x-7' : 'translate-x-1'}`} />
            </div>
          </label>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 bg-accent text-bg text-sm font-semibold px-4 py-2 rounded hover:opacity-80 transition-opacity disabled:opacity-50"
      >
        {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
        {saved ? '저장됨!' : '설정 저장'}
      </button>
    </div>
  )
}
