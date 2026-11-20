import type { AskRecord } from '../api/types'
import { TableView } from './TableView'

interface Props {
  answer: AskRecord
  onFollowUp: (question: string) => void
  disabled?: boolean
}

export function AnswerCard({ answer, onFollowUp, disabled = false }: Props) {
  return (
    <article className="answer card">
      <header>
        <h3>{answer.title}</h3>
        <p className="muted">{answer.question}</p>
      </header>

      {answer.error && <p className="notice notice--warn">{answer.error}</p>}

      {answer.summary.length > 0 && (
        <ul className="answer__summary">
          {answer.summary.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}

      {answer.panels.map((panel) => (
        <TableView key={panel.id} panel={panel} />
      ))}

      {answer.failed_steps.length > 0 && (
        <div className="notice notice--warn">
          {answer.failed_steps.map((step, i) => (
            <p key={i}>{`Could not answer "${step.question}" — ${step.error}`}</p>
          ))}
        </div>
      )}

      {answer.follow_ups.length > 0 && (
        <div className="answer__follow-ups">
          {answer.follow_ups.map((q) => (
            <button key={q} type="button" className="chip" onClick={() => onFollowUp(q)} disabled={disabled}>
              {q}
            </button>
          ))}
        </div>
      )}
    </article>
  )
}
