import React, { useState, useEffect } from 'react'
import { Loader2, CheckCircle2, Circle, RefreshCw, Key, Wifi } from 'lucide-react'

const CATEGORY_LABELS = {
  writing: '글쓰기',
  tts: 'TTS',
  image: '이미지',
  video: '영상',
  multi: '다목적',
}

function ConnectionCard({ conn, onTest, onSaveKey }) {
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [showKeyInput, setShowKeyInput] = useState(false)
  const [keyValue, setKeyValue] = useState('')
  const [saving, setSaving] = useState(false)

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch(`/api/connections/${conn.id}/test`, { method: 'POST' })
      const data = await res.json()
      setTestResult(data)
    } catch (e) {
      setTestResult({ success: false, message: e.message })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!keyValue.trim()) return
    setSaving(true)
    try {
      const res = await fetch(`/api/connections/${conn.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: keyValue }),
      })
      const data = await res.json()
      if (data.success) {
        setShowKeyInput(false)
        setKeyValue('')
        onSaveKey()
      }
    } catch (e) {
      alert('저장 실패: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {conn.connected ? (
            <CheckCircle2 size={16} className="text-success flex-shrink-0" />
          ) : (
            <Circle size={16} className="text-subtext flex-shrink-0" />
          )}
          <div>
            <p className="font-medium text-sm text-text">{conn.name}</p>
            <p className="text-xs text-subtext">{conn.description}</p>
          </div>
        </div>
        <span className={`tag ${conn.connected ? 'badge-done' : 'badge-waiting'}`}>
          {conn.connected ? '연결됨' : '미연결'}
        </span>
      </div>

      {conn.key_masked && (
        <p className="text-xs text-subtext font-mono mb-3">키: {conn.key_masked}</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleTest}
          disabled={testing || !conn.connected}
          className="flex items-center gap-1 text-xs border border-border px-2 py-1 rounded hover:border-accent/50 transition-colors disabled:opacity-40"
        >
          {testing ? <Loader2 size={11} className="animate-spin" /> : <Wifi size={11} />}
          연결 테스트
        </button>
        <button
          onClick={() => setShowKeyInput(!showKeyInput)}
          className="flex items-center gap-1 text-xs border border-border px-2 py-1 rounded hover:border-accent/50 transition-colors"
        >
          <Key size={11} />
          {conn.connected ? 'API 키 변경' : 'API 키 등록'}
        </button>
      </div>

      {testResult && (
        <div className={`mt-2 text-xs px-2 py-1.5 rounded ${testResult.success ? 'bg-success/10 text-success' : 'bg-error/10 text-error'}`}>
          {testResult.message}
        </div>
      )}

      {showKeyInput && (
        <div className="mt-3 flex gap-2">
          <input
            type="password"
            value={keyValue}
            onChange={e => setKeyValue(e.target.value)}
            placeholder="API 키 입력..."
            className="flex-1 bg-bg border border-border rounded px-2 py-1.5 text-xs focus:outline-none focus:border-accent"
            onKeyDown={e => e.key === 'Enter' && handleSave()}
          />
          <button
            onClick={handleSave}
            disabled={saving}
            className="text-xs bg-accent text-bg px-3 py-1.5 rounded font-semibold hover:opacity-80 disabled:opacity-50 transition-opacity"
          >
            {saving ? <Loader2 size={11} className="animate-spin" /> : '저장'}
          </button>
        </div>
      )}
    </div>
  )
}

export default function Connections() {
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchConnections = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/connections')
      const data = await res.json()
      setConnections(data.connections || [])
    } catch (e) {
      console.error('Connections 로드 실패:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchConnections() }, [])

  if (loading) {
    return <div className="flex justify-center py-8"><Loader2 className="animate-spin text-accent" size={24} /></div>
  }

  // 카테고리별 그룹
  const grouped = {}
  connections.forEach(c => {
    const cat = c.category || 'other'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(c)
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-accent">AI 서비스 연결 상태</h3>
        <button onClick={fetchConnections} className="text-xs text-subtext hover:text-accent flex items-center gap-1">
          <RefreshCw size={12} />
          새로고침
        </button>
      </div>

      {Object.entries(grouped).map(([cat, conns]) => (
        <div key={cat}>
          <h4 className="text-xs text-subtext mb-2 uppercase tracking-wide">
            {CATEGORY_LABELS[cat] || cat}
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {conns.map(conn => (
              <ConnectionCard
                key={conn.id}
                conn={conn}
                onTest={() => {}}
                onSaveKey={fetchConnections}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
