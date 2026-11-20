import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { useApi } from '../api/ApiProvider'
import type { AskRecord } from '../api/types'
import { AnswerCard } from './AnswerCard'

export function AskPanel({ workspaceId }: { workspaceId: string }) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [recent, setRecent] = useState<AskRecord[]>([])

  const history = useQuery({
    queryKey: ['questions', workspaceId],
    queryFn: () => api.listQuestions(workspaceId),
  })
  const ask = useMutation({
    mutationFn: (question: string) => api.ask(workspaceId, question),
    onSuccess: (record) => {
      setText('')
      setRecent((current) => [record, ...current])
      void queryClient.invalidateQueries({ queryKey: ['questions', workspaceId] })
    },
  })

  function submit(question: string) {
    const trimmed = question.trim()
    if (trimmed && !ask.isPending) ask.mutate(trimmed)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    submit(text)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit(text)
    }
  }

  const seen = new Set(recent.map((r) => r.id))
  const answers = [...recent, ...(history.data ?? []).filter((r) => !seen.has(r.id))]

  return (
    <section className="ask">
      <form className="ask__form" onSubmit={onSubmit}>
        <textarea
          aria-label="Question"
          placeholder="Ask about your data, e.g. “Which customers spent the most?”"
          value={text}
          rows={2}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" disabled={!text.trim() || ask.isPending}>
          {ask.isPending ? 'Thinking…' : 'Ask'}
        </button>
      </form>
      {ask.isError && <p role="alert">{ask.error.message}</p>}

      <div className="ask__answers">
        {answers.map((record) => (
          <AnswerCard key={record.id} answer={record} onFollowUp={submit} disabled={ask.isPending} />
        ))}
      </div>
    </section>
  )
}
