import React, { useState } from 'react'
import { LayoutDashboard, FileText, BarChart2, BookOpen, Settings, ScrollText, UserCheck } from 'lucide-react'
import Overview from './pages/Overview.jsx'
import Content from './pages/Content.jsx'
import Analytics from './pages/Analytics.jsx'
import Novel from './pages/Novel.jsx'
import SettingsPage from './pages/Settings.jsx'
import Logs from './pages/Logs.jsx'
import Assist from './pages/Assist.jsx'

const TABS = [
  { id: 'overview', label: '개요', icon: LayoutDashboard, component: Overview },
  { id: 'content', label: '콘텐츠', icon: FileText, component: Content },
  { id: 'assist', label: '수동모드', icon: UserCheck, component: Assist },
  { id: 'analytics', label: '분석', icon: BarChart2, component: Analytics },
  { id: 'novel', label: '소설', icon: BookOpen, component: Novel },
  { id: 'settings', label: '설정', icon: Settings, component: SettingsPage },
  { id: 'logs', label: '로그', icon: ScrollText, component: Logs },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const [systemStatus, setSystemStatus] = useState('ok') // ok | warn | error

  const ActiveComponent = TABS.find(t => t.id === activeTab)?.component || Overview

  return (
    <div className="flex flex-col h-screen bg-bg text-text overflow-hidden">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-border bg-card flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-accent font-bold text-base md:text-lg tracking-tight">
            The 4th Path
          </span>
          <span className="hidden md:inline text-subtext text-xs">· Control Panel</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${systemStatus === 'ok' ? 'bg-success' : systemStatus === 'warn' ? 'bg-warning' : 'bg-error'}`}></span>
          <span className="text-xs text-subtext hidden sm:inline">
            {systemStatus === 'ok' ? 'System OK' : systemStatus === 'warn' ? '경고' : '오류'}
          </span>
        </div>
      </header>

      {/* 탭 네비게이션 */}
      <nav className="flex border-b border-border bg-card flex-shrink-0 overflow-x-auto">
        {TABS.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 md:px-5 py-3 text-xs md:text-sm font-medium whitespace-nowrap transition-colors border-b-2 ${
                isActive
                  ? 'border-accent text-accent'
                  : 'border-transparent text-subtext hover:text-text'
              }`}
            >
              <Icon size={15} />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          )
        })}
      </nav>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 overflow-y-auto">
        <ActiveComponent />
      </main>
    </div>
  )
}
