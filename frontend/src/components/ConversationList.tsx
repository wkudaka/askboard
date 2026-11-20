import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useApi } from '../api/ApiProvider'
import type { Conversation } from '../api/types'
import { groupByDate } from '../lib/dates'
import { PencilIcon, TrashIcon } from './icons'

interface Props {
  workspaceId: string
  activeId: string | null
  onSelect: (conversationId: string | null) => void
}

function Item({
  conversation,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  conversation: Conversation
  active: boolean
  onSelect: () => void
  onRename: (title: string) => void
  onDelete: () => void
}) {
  const [mode, setMode] = useState<'view' | 'rename' | 'confirm'>('view')
  const [draft, setDraft] = useState(conversation.title)
  // Enter submits and then unmounts the input, which also fires blur: save only once.
  const editing = useRef(false)

  function startRename() {
    editing.current = true
    setDraft(conversation.title)
    setMode('rename')
  }

  function save(event?: FormEvent) {
    event?.preventDefault()
    if (!editing.current) return
    editing.current = false
    const title = draft.trim()
    if (title && title !== conversation.title) onRename(title)
    setMode('view')
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      editing.current = false
      setDraft(conversation.title)
      setMode('view')
    }
  }

  const className = `conversation${active ? ' conversation--active' : ''}`

  if (mode === 'rename') {
    return (
      <li className={className}>
        <form onSubmit={save} className="conversation__rename">
          <input
            aria-label="Chat title"
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => save()}
            onKeyDown={onKeyDown}
          />
        </form>
      </li>
    )
  }

  if (mode === 'confirm') {
    return (
      <li className={`${className} conversation--confirm`}>
        <span className="conversation__title">Delete “{conversation.title}”?</span>
        <span className="conversation__confirm">
          <button type="button" className="button--danger" onClick={onDelete}>
            Delete
          </button>
          <button type="button" className="button--secondary" onClick={() => setMode('view')}>
            Cancel
          </button>
        </span>
      </li>
    )
  }

  return (
    <li className={className}>
      <button
        type="button"
        className="conversation__open"
        aria-current={active ? 'page' : undefined}
        onClick={onSelect}
        title={conversation.title}
      >
        <span className="conversation__title">{conversation.title}</span>
      </button>
      <span className="conversation__actions">
        <button
          type="button"
          className="icon-button icon-button--small"
          aria-label={`Rename ${conversation.title}`}
          onClick={startRename}
        >
          <PencilIcon />
        </button>
        <button
          type="button"
          className="icon-button icon-button--small"
          aria-label={`Delete ${conversation.title}`}
          onClick={() => setMode('confirm')}
        >
          <TrashIcon />
        </button>
      </span>
    </li>
  )
}

export function ConversationList({ workspaceId, activeId, onSelect }: Props) {
  const api = useApi()
  const queryClient = useQueryClient()
  const key = ['conversations', workspaceId]

  const conversations = useQuery({ queryKey: key, queryFn: () => api.listConversations(workspaceId) })

  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => api.renameConversation(workspaceId, id, title),
    onSuccess: (updated) => {
      queryClient.setQueryData<Conversation[]>(key, (old) => old?.map((c) => (c.id === updated.id ? updated : c)))
    },
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteConversation(workspaceId, id),
    onSuccess: (_, id) => {
      queryClient.setQueryData<Conversation[]>(key, (old) => old?.filter((c) => c.id !== id))
      queryClient.removeQueries({ queryKey: ['conversation', workspaceId, id] })
      if (id === activeId) onSelect(null)
    },
  })

  if (conversations.isPending) return <p className="sidebar__note">Loading chats…</p>
  if (conversations.isError) return <p role="alert" className="sidebar__note">{conversations.error.message}</p>
  if (conversations.data.length === 0) return <p className="sidebar__note">No chats yet.</p>

  return (
    <>
      {(rename.isError || remove.isError) && (
        <p role="alert" className="sidebar__note">
          {(rename.error ?? remove.error)?.message}
        </p>
      )}
      {groupByDate(conversations.data, (c) => c.updated_at).map((group) => (
        <section key={group.label} className="conversation-group" aria-label={group.label}>
          <h3>{group.label}</h3>
          <ul>
            {group.items.map((c) => (
              <Item
                key={c.id}
                conversation={c}
                active={c.id === activeId}
                onSelect={() => onSelect(c.id)}
                onRename={(title) => rename.mutate({ id: c.id, title })}
                onDelete={() => remove.mutate(c.id)}
              />
            ))}
          </ul>
        </section>
      ))}
    </>
  )
}
