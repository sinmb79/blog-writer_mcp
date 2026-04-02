import React, { useState } from 'react'
import Connections from './settings/Connections.jsx'
import ToolSelect from './settings/ToolSelect.jsx'
import Distribution from './settings/Distribution.jsx'
import Quality from './settings/Quality.jsx'
import CostMonitor from './settings/CostMonitor.jsx'

const SUB_TABS = [
  { id: 'connections', label: 'AI 연결', component: Connections },
  { id: 'tools', label: '생성도구', component: ToolSelect },
  { id: 'distribution', label: '배포채널', component: Distribution },
  { id: 'quality', label: '품질·스케줄', component: Quality },
  { id: 'cost', label: '비용관리', component: CostMonitor },
]

export default function Settings() {
  const [activeSubTab, setActiveSubTab] = useState('connections')

  const ActiveSub = SUB_TABS.find(t => t.id === activeSubTab)?.component || Connections

  return (
    <div className="p-4 md:p-6">
      <h1 className="text-lg font-bold mb-4">설정</h1>

      {/* 서브탭 */}
      <div className="flex gap-1 mb-5 flex-wrap">
        {SUB_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={`px-4 py-2 text-xs rounded-lg font-medium transition-colors ${
              activeSubTab === tab.id
                ? 'bg-accent text-bg'
                : 'bg-card border border-border text-subtext hover:text-text hover:border-accent/50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 서브탭 내용 */}
      <ActiveSub />
    </div>
  )
}
