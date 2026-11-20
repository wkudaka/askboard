import { useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { PaperclipIcon, SendIcon } from './icons'

interface Props {
  onSubmit: (question: string) => void
  busy: boolean
  onAttach?: () => void
  placeholder?: string
  autoFocus?: boolean
}

const MAX_HEIGHT = 200

export function Composer({ onSubmit, busy, onAttach, placeholder = 'Ask anything about your data', autoFocus }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  // Grow with the content, like a chat box, up to MAX_HEIGHT.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [text])

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    onSubmit(trimmed)
    setText('')
  }

  function onFormSubmit(event: FormEvent) {
    event.preventDefault()
    submit()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className="composer" onSubmit={onFormSubmit}>
      {onAttach && (
        <button type="button" className="icon-button" aria-label="Upload CSV" title="Upload CSV" onClick={onAttach}>
          <PaperclipIcon />
        </button>
      )}
      <textarea
        ref={ref}
        aria-label="Question"
        placeholder={placeholder}
        value={text}
        rows={1}
        autoFocus={autoFocus}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <button
        type="submit"
        className="composer__send"
        aria-label="Send"
        title="Send"
        disabled={!text.trim() || busy}
      >
        <SendIcon />
      </button>
    </form>
  )
}
