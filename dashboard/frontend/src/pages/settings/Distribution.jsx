import React, { useState, useEffect } from 'react'
import { Loader2, Save, Globe } from 'lucide-react'

const PLATFORMS = [
  { id: 'blogger', label: '블로거 (Blogger)', icon: '📝' },
  { id: 'youtube', label: 'YouTube Shorts', icon: '▶️' },
  { id: 'instagram', label: 'Instagram Reels', icon: '📸' },
  { id: 'x', label: 'X (Twitter)', icon: '🐦' },
  { id: 'tiktok', label: 'TikTok', icon: '🎵' },
  { id: 'novel', label: '노벨피아', icon: '📖' },
]

export default function Distribution() {
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

  const togglePlatform = (id) => {
    setSettings(s => ({
      ...s,
      publishing: {
        ...s.publishing,
        [id]: {
          ...(s.publishing?.[id] || {}),
          enabled: !(s.publishing?.[id]?.enabled ?? false),
        },
      },
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

  const publishing = settings?.publishing || {}
  const schedule = settings?.schedule || {}

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-accent flex items-center gap-2">
        <Globe size={14} />
        배포 채널 설정
      </h3>

      {/* 플랫폼 ON/OFF */}
      <div className="card p-4">
        <h4 className="text-sm font-medium text-text mb-3">발행 채널</h4>
        <div className="space-y-3">
          {PLATFORMS.map(platform => {
            const enabled = publishing[platform.id]?.enabled ?? false
            return (
              <div key={platform.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                <div className="flex items-center gap-2">
                  <span>{platform.icon}</span>
                  <span className="text-sm text-text">{platform.label}</span>
                </div>
                <button
                  onClick={() => togglePlatform(platform.id)}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    enabled ? 'bg-success' : 'bg-border'
                  }`}
                >
                  <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    enabled ? 'translate-x-7' : 'translate-x-1'
                  }`} />
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* 시차 배포 스케줄 */}
      <div className="card p-4">
        <h4 className="text-sm font-medium text-text mb-3">발행 시각 설정</h4>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { key: 'collector', label: '수집' },
            { key: 'writer', label: '글쓰기' },
            { key: 'converter', label: '변환' },
            { key: 'publisher', label: '발행' },
            { key: 'youtube_uploader', label: 'YouTube 업로드' },
            { key: 'analytics', label: '분석' },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs text-subtext mb-1">{label}</label>
              <input
                type="time"
                value={schedule[key] || ''}
                onChange={e => updateSchedule(key, e.target.value)}
                className="w-full bg-bg border border-border rounded px-2 py-1.5 text-sm text-text focus:outline-none focus:border-accent"
              />
            </div>
          ))}
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
