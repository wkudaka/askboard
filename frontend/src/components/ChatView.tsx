import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useApi } from '../api/ApiProvider'
import type { AskRecord, ConversationDetail, Workspace } from '../api/types'
import { suggestQuestions } from '../lib/suggestions'
import { AnswerCard } from './AnswerCard'
import { Composer } from './Composer'
import { SparkIcon } from './icons'

interface Props {
  workspace: Workspace
  conversationId: string | null
  onConversationStarted: (conversationId: string) => void
  onOpenData: () => void
}

interface Pending {
  question: string
  conversationId: string | null
}

function UserMessage({ text }: { text: string }) {
  return (
    <div className="message message--user">
      <p className="message__bubble">{text}</p>
    </div>
  )
}

function Thinking() {
  return (
    <div className="message message--assistant" role="status" aria-label="Thinking">
      <div className="message__avatar">
        <SparkIcon />
      </div>
      <span className="typing" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </div>
  )
}

export function ChatView({ workspace, conversationId, onConversationStarted, onOpenData }: Props) {
  const api = useApi()
  const queryClient = useQueryClient()
  const workspaceId = workspace.id
  const [failed, setFailed] = useState<{ pending: Pending; message: string } | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  // Where the user is now: an answer for a new chat only opens it if they are still on "new chat".
  const current = useRef(conversationId)
  useEffect(() => {
    current.current = conversationId
  }, [conversationId])

  const datasets = useQuery({
    queryKey: ['datasets', workspaceId],
    queryFn: () => api.listDatasets(workspaceId),
  })
  const detail = useQuery({
    queryKey: ['conversation', workspaceId, conversationId],
    queryFn: () => api.getConversation(workspaceId, conversationId!),
    enabled: conversationId !== null,
  })

  const ask = useMutation({
    mutationFn: (p: Pending) => api.ask(workspaceId, p.question, p.conversationId),
    onMutate: () => setFailed(null),
    onSuccess: (record: AskRecord, p) => {
      const key = ['conversation', workspaceId, record.conversation_id]
      queryClient.setQueryData<ConversationDetail>(key, (old) =>
        old
          ? { ...old, updated_at: record.created_at, messages: [...old.messages.filter((m) => m.id !== record.id), record] }
          : {
              id: record.conversation_id,
              workspace_id: workspaceId,
              title: record.question,
              created_at: record.created_at,
              updated_at: record.created_at,
              messages: [record],
            },
      )
      void queryClient.invalidateQueries({ queryKey: ['conversations', workspaceId] })
      if (p.conversationId === null && current.current === null) onConversationStarted(record.conversation_id)
    },
    onError: (error, p) => setFailed({ pending: p, message: error.message }),
  })

  const pending = ask.isPending && ask.variables.conversationId === conversationId ? ask.variables : null
  const failure = failed && failed.pending.conversationId === conversationId ? failed : null
  const messages = conversationId ? (detail.data?.messages ?? []) : []

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'end' })
  }, [messages.length, pending, failure, conversationId])

  function send(question: string) {
    if (!ask.isPending) ask.mutate({ question, conversationId })
  }

  const loadedTables = (datasets.data ?? []).filter((d) => d.status === 'loaded')
  const isEmpty = conversationId === null && !pending && !failure

  if (isEmpty) {
    const suggestions = suggestQuestions(loadedTables)
    return (
      <div className="chat chat--empty">
        <div className="hero">
          <h2>What do you want to know?</h2>
          <p className="muted">
            {loadedTables.length === 0
              ? `Workspace “${workspace.name}” has no data yet. Upload a CSV to get started.`
              : `Ask about ${loadedTables.map((d) => d.table_name).join(', ')} in plain language.`}
          </p>
          <Composer onSubmit={send} busy={ask.isPending} onAttach={onOpenData} autoFocus />
          <div className="hero__suggestions">
            {loadedTables.length === 0 ? (
              <button type="button" className="chip" onClick={onOpenData}>
                Upload a CSV
              </button>
            ) : (
              suggestions.map((q) => (
                <button key={q} type="button" className="chip" onClick={() => send(q)} disabled={ask.isPending}>
                  {q}
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="chat">
      <div className="chat__scroll">
        <div className="thread">
          {detail.isPending && conversationId !== null && <p className="muted">Loading conversation…</p>}
          {detail.isError && <p role="alert">{detail.error.message}</p>}

          {messages.map((record, i) => (
            <div key={record.id} className="turn">
              <UserMessage text={record.question} />
              <AnswerCard
                answer={record}
                onFollowUp={send}
                disabled={ask.isPending}
                showFollowUps={i === messages.length - 1 && !pending && !failure}
              />
            </div>
          ))}

          {pending && (
            <div className="turn">
              <UserMessage text={pending.question} />
              <Thinking />
            </div>
          )}

          {failure && (
            <div className="turn">
              <UserMessage text={failure.pending.question} />
              <div className="message message--assistant">
                <div className="message__avatar">
                  <SparkIcon />
                </div>
                <div className="message__error">
                  <p role="alert">{failure.message}</p>
                  <button
                    type="button"
                    className="button--secondary"
                    onClick={() => ask.mutate(failure.pending)}
                    disabled={ask.isPending}
                  >
                    Retry
                  </button>
                </div>
              </div>
            </div>
          )}
          <div ref={bottom} />
        </div>
      </div>
      <div className="chat__footer">
        <Composer onSubmit={send} busy={ask.isPending} onAttach={onOpenData} placeholder="Ask a follow-up" />
        <p className="chat__disclaimer">Answers are generated by an AI model. Check the SQL behind each chart.</p>
      </div>
    </div>
  )
}
