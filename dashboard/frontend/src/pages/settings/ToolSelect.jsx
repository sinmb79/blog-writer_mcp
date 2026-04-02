import React, { useState, useEffect } from 'react'
import { Loader2, Save } from 'lucide-react'

export default function ToolSelect() {
  const [tools, setTools] = useState({})
  const [selected, setSelected] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch('/api/tools')
      .then(r => r.json())
      .then(d => {
        setTools(d.tools || {})
        const initial = {}
        Object.entries(d.tools || {}).forEach(([k, v]) => {
          initial[k] = v.current
        })
        setSelected(initial)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch('/api/tools', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tools: selected }),
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

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-accent">생성 도구 선택</h3>

      {Object.entries(tools).map(([category, data]) => (
        <div key={category} className="card p-4">
          <h4 className="text-sm font-medium text-text mb-3">{data.label}</h4>
          <div className="space-y-2">
            {data.options.map(opt => (
              <label
                key={opt.value}
                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                  selected[category] === opt.value
                    ? 'bg-accent/10 border border-accent/30'
                    : 'border border-transparent hover:bg-card-hover'
                }`}
              >
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                  selected[category] === opt.value
                    ? 'border-accent'
                    : 'border-subtext'
                }`}>
                  {selected[category] === opt.value && (
                    <div className="w-2 h-2 rounded-full bg-accent" />
                  )}
                </div>
                <input
                  type="radio"
                  name={category}
                  value={opt.value}
                  checked={selected[category] === opt.value}
                  onChange={() => setSelected(s => ({ ...s, [category]: opt.value }))}
                  className="sr-only"
                />
                <span className="text-sm text-text">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>
      ))}

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
