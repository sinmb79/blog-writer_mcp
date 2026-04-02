import { useState, useEffect, useRef } from 'react'
import {
  Link2, Upload, FolderOpen, RefreshCw, Trash2,
  CheckCircle, Clock, AlertCircle, Loader, ChevronDown,
  ChevronUp, Copy, Image, Video, FileText, Plus, X
} from 'lucide-react'

const API = ''

const STATUS_COLOR = {
  pending:    '#888880',
  fetching:   '#4a5abf',
  generating: '#c8a84e',
  awaiting:   '#c8a84e',
  assembling: '#4a5abf',
  ready:      '#3a7d5c',
  error:      '#bf3a3a',
}

const STATUS_ICON = {
  pending:    <Clock size={14} />,
  fetching:   <Loader size={14} className="spin" />,
  generating: <Loader size={14} className="spin" />,
  awaiting:   <Upload size={14} />,
  assembling: <Loader size={14} className="spin" />,
  ready:      <CheckCircle size={14} />,
  error:      <AlertCircle size={14} />,
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button onClick={copy} style={{
      background: 'none', border: '1px solid #333', borderRadius: 4,
      color: copied ? '#3a7d5c' : '#888', cursor: 'pointer',
      padding: '2px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4
    }}>
      <Copy size={11} /> {copied ? '복사됨' : '복사'}
    </button>
  )
}

function PromptCard({ prompt, index }) {
  return (
    <div style={{
      background: '#0f0f14', border: '1px solid #2a2a32',
      borderRadius: 8, padding: 12, marginBottom: 8
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 11, color: '#c8a84e', fontWeight: 600 }}>
          <Image size={11} style={{ display: 'inline', marginRight: 4 }} />
          이미지 #{index + 1} — {prompt.purpose}
        </span>
        <CopyBtn text={prompt.en} />
      </div>
      <div style={{ fontSize: 12, color: '#b0b0a8', marginBottom: 4 }}>
        <span style={{ color: '#666', marginRight: 6 }}>KO</span>{prompt.ko}
      </div>
      <div style={{ fontSize: 12, color: '#e0e0d8' }}>
        <span style={{ color: '#666', marginRight: 6 }}>EN</span>{prompt.en}
      </div>
    </div>
  )
}

function AssetDropZone({ sessionId, onUploaded }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef()

  const handleFiles = async (files) => {
    setUploading(true)
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('asset_type', file.type.startsWith('video') ? 'video' : 'image')
      await fetch(`${API}/api/assist/session/${sessionId}/upload`, { method: 'POST', body: fd })
    }
    setUploading(false)
    onUploaded()
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); handleFiles([...e.dataTransfer.files]) }}
      onClick={() => inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragging ? '#c8a84e' : '#333'}`,
        borderRadius: 8, padding: '20px 16px', textAlign: 'center',
        cursor: 'pointer', background: dragging ? '#1a1a0a' : 'transparent',
        transition: 'all 0.2s',
      }}
    >
      <input ref={inputRef} type="file" multiple accept="image/*,video/*"
        style={{ display: 'none' }}
        onChange={e => handleFiles([...e.target.files])} />
      {uploading
        ? <><Loader size={20} style={{ color: '#c8a84e', marginBottom: 6 }} /><div style={{ color: '#888', fontSize: 12 }}>업로드 중...</div></>
        : <>
          <Upload size={20} style={{ color: '#555', marginBottom: 6 }} />
          <div style={{ color: '#888', fontSize: 12 }}>이미지 / 영상 드래그 앤 드롭 또는 클릭하여 선택</div>
          <div style={{ color: '#555', fontSize: 11, marginTop: 4 }}>JPG, PNG, WebP, MP4, MOV 지원</div>
        </>
      }
    </div>
  )
}

function SessionCard({ session: initial, onDelete }) {
  const [session, setSession] = useState(initial)
  const [open, setOpen] = useState(initial.status === 'awaiting')
  const [refreshing, setRefreshing] = useState(false)

  const refresh = async () => {
    setRefreshing(true)
    const r = await fetch(`${API}/api/assist/session/${session.session_id}`)
    if (r.ok) setSession(await r.json())
    setRefreshing(false)
  }

  // 처리 중이면 자동 폴링
  useEffect(() => {
    const active = ['pending', 'fetching', 'generating']
    if (!active.includes(session.status)) return
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [session.status])

  const removeAsset = async (filename) => {
    await fetch(`${API}/api/assist/session/${session.session_id}/asset/${filename}`, { method: 'DELETE' })
    refresh()
  }

  const color = STATUS_COLOR[session.status] || '#888'
  const icon  = STATUS_ICON[session.status]
  const prompts = session.prompts || {}
  const imagePrompts = prompts.image_prompts || []
  const videoPrompt  = prompts.video_prompt || null
  const narration    = prompts.narration_script || ''
  const assets       = session.assets || []

  return (
    <div style={{
      background: '#111116', border: '1px solid #222228',
      borderRadius: 10, marginBottom: 12, overflow: 'hidden'
    }}>
      {/* 헤더 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '12px 16px', cursor: 'pointer',
      }} onClick={() => setOpen(o => !o)}>
        <div style={{ color, display: 'flex', alignItems: 'center' }}>{icon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e0e0d8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {session.title || session.url}
          </div>
          <div style={{ fontSize: 11, color: '#555', marginTop: 2 }}>
            {new Date(session.created_at).toLocaleString('ko-KR')}
            {' · '}
            <span style={{ color }}>{session.status_label || session.status}</span>
            {assets.length > 0 && <span style={{ color: '#3a7d5c' }}> · 에셋 {assets.length}개</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button onClick={e => { e.stopPropagation(); refresh() }}
            style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', padding: 4 }}>
            <RefreshCw size={13} className={refreshing ? 'spin' : ''} />
          </button>
          <button onClick={e => { e.stopPropagation(); onDelete(session.session_id) }}
            style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', padding: 4 }}>
            <Trash2 size={13} />
          </button>
          {open ? <ChevronUp size={14} color="#555" /> : <ChevronDown size={14} color="#555" />}
        </div>
      </div>

      {/* 본문 */}
      {open && (
        <div style={{ borderTop: '1px solid #1a1a20', padding: 16 }}>
          {session.status === 'error' && (
            <div style={{ background: '#1a0808', border: '1px solid #bf3a3a', borderRadius: 6, padding: 10, marginBottom: 12, fontSize: 12, color: '#bf3a3a' }}>
              {session.error}
            </div>
          )}

          {session.body_preview && (
            <div style={{ fontSize: 12, color: '#666', marginBottom: 14, lineHeight: 1.6 }}>
              {session.body_preview}…
            </div>
          )}

          {/* 프롬프트 섹션 */}
          {imagePrompts.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#888', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Image size={13} /> 이미지 프롬프트
              </div>
              {imagePrompts.map((p, i) => <PromptCard key={i} prompt={p} index={i} />)}
            </div>
          )}

          {videoPrompt && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#888', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Video size={13} /> 영상 프롬프트
              </div>
              <div style={{ background: '#0f0f14', border: '1px solid #2a2a32', borderRadius: 8, padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: '#4a5abf' }}>Sora / Runway / Veo</span>
                  <CopyBtn text={videoPrompt.en} />
                </div>
                <div style={{ fontSize: 12, color: '#b0b0a8', marginBottom: 4 }}>
                  <span style={{ color: '#666', marginRight: 6 }}>KO</span>{videoPrompt.ko}
                </div>
                <div style={{ fontSize: 12, color: '#e0e0d8' }}>
                  <span style={{ color: '#666', marginRight: 6 }}>EN</span>{videoPrompt.en}
                </div>
              </div>
            </div>
          )}

          {narration && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#888', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <FileText size={13} /> 나레이션 스크립트
              </div>
              <div style={{ background: '#0f0f14', border: '1px solid #2a2a32', borderRadius: 8, padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
                  <CopyBtn text={narration} />
                </div>
                <div style={{ fontSize: 12, color: '#e0e0d8', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                  {narration}
                </div>
              </div>
            </div>
          )}

          {/* 에셋 업로드 */}
          {['awaiting', 'ready', 'generating'].includes(session.status) && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#888', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Upload size={13} /> 에셋 제공
              </div>
              <AssetDropZone sessionId={session.session_id} onUploaded={refresh} />
            </div>
          )}

          {/* 등록된 에셋 */}
          {assets.length > 0 && (
            <div>
              <div style={{ fontSize: 12, color: '#888', fontWeight: 600, marginBottom: 8 }}>
                등록된 에셋 ({assets.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {assets.map((a, i) => (
                  <div key={i} style={{
                    background: '#0f0f14', border: '1px solid #2a2a32',
                    borderRadius: 6, padding: '6px 10px', fontSize: 11,
                    display: 'flex', alignItems: 'center', gap: 6
                  }}>
                    {a.type === 'video' ? <Video size={11} color="#4a5abf" /> : <Image size={11} color="#3a7d5c" />}
                    <span style={{ color: '#b0b0a8', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.filename}
                    </span>
                    <button onClick={() => removeAsset(a.filename)}
                      style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', padding: 0 }}>
                      <X size={11} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Assist() {
  const [url, setUrl] = useState('')
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)
  const [inboxPath, setInboxPath] = useState('')

  const load = async () => {
    const [s, i] = await Promise.all([
      fetch(`${API}/api/assist/sessions`).then(r => r.json()).catch(() => []),
      fetch(`${API}/api/assist/inbox`).then(r => r.json()).catch(() => ({})),
    ])
    setSessions(s)
    setInboxPath(i.path || '')
  }

  useEffect(() => { load() }, [])

  const submit = async () => {
    if (!url.trim()) return
    setLoading(true)
    await fetch(`${API}/api/assist/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url.trim() }),
    })
    setUrl('')
    await load()
    setLoading(false)
  }

  const deleteSession = async (sid) => {
    if (!confirm('이 세션을 삭제하시겠습니까?')) return
    await fetch(`${API}/api/assist/session/${sid}`, { method: 'DELETE' })
    load()
  }

  return (
    <div style={{ padding: '24px 28px', maxWidth: 820, margin: '0 auto' }}>
      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: '#e0e0d8', margin: 0 }}>
          수동(어시스트) 모드
        </h2>
        <p style={{ fontSize: 13, color: '#666', marginTop: 6 }}>
          직접 작성한 블로그 글 URL을 입력하면 시스템이 이미지·영상 프롬프트를 생성합니다.
          생성한 에셋을 업로드하면 쇼츠 조립·배포 파이프라인으로 연결됩니다.
        </p>
      </div>

      {/* URL 입력 */}
      <div style={{
        background: '#111116', border: '1px solid #222228',
        borderRadius: 10, padding: 16, marginBottom: 16
      }}>
        <div style={{ fontSize: 12, color: '#888', marginBottom: 8, fontWeight: 600 }}>
          <Link2 size={12} style={{ display: 'inline', marginRight: 6 }} />
          블로그 글 URL
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="https://www.the4thpath.com/2026/03/..."
            style={{
              flex: 1, background: '#0a0a0d', border: '1px solid #333',
              borderRadius: 6, padding: '8px 12px', color: '#e0e0d8',
              fontSize: 13, outline: 'none',
            }}
          />
          <button
            onClick={submit}
            disabled={loading || !url.trim()}
            style={{
              background: loading ? '#333' : '#c8a84e',
              color: loading ? '#888' : '#0a0a0d',
              border: 'none', borderRadius: 6, padding: '8px 16px',
              fontWeight: 700, fontSize: 13, cursor: loading ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {loading ? <><Loader size={13} className="spin" /> 분석 중</> : <><Plus size={13} /> 분석 시작</>}
          </button>
        </div>
      </div>

      {/* inbox 폴더 안내 */}
      {inboxPath && (
        <div style={{
          background: '#0d0d10', border: '1px solid #1e2a1e',
          borderRadius: 8, padding: '10px 14px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 10
        }}>
          <FolderOpen size={14} color="#3a7d5c" />
          <div>
            <span style={{ fontSize: 11, color: '#3a7d5c', fontWeight: 600 }}>폴더 드롭 경로</span>
            <span style={{ fontSize: 11, color: '#666', marginLeft: 8 }}>{inboxPath}</span>
          </div>
          <div style={{ fontSize: 11, color: '#555', marginLeft: 'auto' }}>
            파일명 앞 8자리에 세션 ID를 포함하면 자동 연결됩니다
          </div>
        </div>
      )}

      {/* 세션 목록 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: '#888', fontWeight: 600 }}>
          세션 목록 ({sessions.length})
        </span>
        <button onClick={load} style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
          <RefreshCw size={12} /> 새로고침
        </button>
      </div>

      {sessions.length === 0
        ? <div style={{ textAlign: 'center', color: '#444', padding: '40px 0', fontSize: 13 }}>
            아직 세션이 없습니다. URL을 입력해 시작하세요.
          </div>
        : sessions.map(s => (
            <SessionCard key={s.session_id} session={s} onDelete={deleteSession} />
          ))
      }

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
