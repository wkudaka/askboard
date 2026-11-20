import { useQuery } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useApi } from './api/ApiProvider'
import { ApiStatus } from './components/ApiStatus'
import { ChatView } from './components/ChatView'
import { ConversationList } from './components/ConversationList'
import { DataDrawer } from './components/DataDrawer'
import { DatabaseIcon, NewChatIcon, SidebarIcon } from './components/icons'
import { WorkspacePicker } from './components/WorkspacePicker'

const WIDE = '(min-width: 768px)'

function isWide(): boolean {
  return typeof window.matchMedia !== 'function' || window.matchMedia(WIDE).matches
}

export default function App() {
  const api = useApi()
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(isWide)
  const [dataOpen, setDataOpen] = useState(false)

  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api.listWorkspaces() })
  const workspace = workspaces.data?.find((w) => w.id === workspaceId) ?? null
  const datasets = useQuery({
    queryKey: ['datasets', workspaceId],
    queryFn: () => api.listDatasets(workspaceId!),
    enabled: workspaceId !== null,
  })
  const conversationTitle = useQuery({
    queryKey: ['conversations', workspaceId],
    queryFn: () => api.listConversations(workspaceId!),
    enabled: workspaceId !== null,
    select: (list) => list.find((c) => c.id === conversationId)?.title,
  }).data

  const changeWorkspace = useCallback((id: string) => {
    setWorkspaceId(id)
    setConversationId(null)
  }, [])

  const openConversation = useCallback((id: string | null) => {
    setConversationId(id)
    if (!isWide()) setSidebarOpen(false)
  }, [])

  const closeData = useCallback(() => setDataOpen(false), [])
  const datasetCount = datasets.data?.length ?? 0

  return (
    <div className={`shell${sidebarOpen ? ' shell--sidebar-open' : ''}`}>
      <aside className="sidebar" aria-label="Sidebar" hidden={!sidebarOpen}>
        <div className="sidebar__top">
          <h1 className="sidebar__brand">Askboard</h1>
          <button
            type="button"
            className="icon-button"
            aria-label="Close sidebar"
            title="Close sidebar"
            onClick={() => setSidebarOpen(false)}
          >
            <SidebarIcon />
          </button>
        </div>

        <WorkspacePicker value={workspaceId} onChange={changeWorkspace} />

        {workspaceId && (
          <>
            <nav className="sidebar__actions">
              <button type="button" className="sidebar__item" onClick={() => openConversation(null)}>
                <NewChatIcon />
                <span>New chat</span>
              </button>
              <button
                type="button"
                className="sidebar__item"
                onClick={() => {
                  setDataOpen(true)
                  if (!isWide()) setSidebarOpen(false)
                }}
              >
                <DatabaseIcon />
                <span>Data</span>
                {datasetCount > 0 && <span className="sidebar__count">{datasetCount}</span>}
              </button>
            </nav>
            <nav className="sidebar__chats" aria-label="Chats">
              <ConversationList
                key={workspaceId}
                workspaceId={workspaceId}
                activeId={conversationId}
                onSelect={openConversation}
              />
            </nav>
          </>
        )}

        <footer className="sidebar__footer">
          <ApiStatus />
        </footer>
      </aside>
      {sidebarOpen && <div className="sidebar__scrim" onClick={() => setSidebarOpen(false)} />}

      <main className="main">
        <header className="topbar">
          {!sidebarOpen && (
            <>
              <button
                type="button"
                className="icon-button"
                aria-label="Open sidebar"
                title="Open sidebar"
                onClick={() => setSidebarOpen(true)}
              >
                <SidebarIcon />
              </button>
              {workspaceId && (
                <button
                  type="button"
                  className="icon-button"
                  aria-label="New chat"
                  title="New chat"
                  onClick={() => openConversation(null)}
                >
                  <NewChatIcon />
                </button>
              )}
            </>
          )}
          <span className="topbar__title">
            {conversationId ? (conversationTitle ?? '') : (workspace?.name ?? 'Askboard')}
          </span>
        </header>

        {workspace ? (
          <ChatView
            key={workspace.id}
            workspace={workspace}
            conversationId={conversationId}
            onConversationStarted={setConversationId}
            onOpenData={() => setDataOpen(true)}
          />
        ) : (
          <div className="chat chat--empty">
            <div className="hero">
              <h2>Welcome to Askboard</h2>
              <p className="muted">
                Upload your CSVs, ask questions in plain language, get a dashboard. Create a workspace in the
                sidebar to begin.
              </p>
              {!sidebarOpen && (
                <button type="button" onClick={() => setSidebarOpen(true)}>
                  Open sidebar
                </button>
              )}
            </div>
          </div>
        )}
      </main>

      {workspaceId && <DataDrawer key={workspaceId} workspaceId={workspaceId} open={dataOpen} onClose={closeData} />}
    </div>
  )
}
