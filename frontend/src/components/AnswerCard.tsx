import type { AskRecord } from '../api/types'
import { SparkIcon } from './icons'
import { PanelView } from './panels/PanelView'

interface Props {
  answer: AskRecord
  onFollowUp: (question: string) => void
  disabled?: boolean
  /** Follow-up chips are only offered on the latest answer, like a chat assistant. */
  showFollowUps?: boolean
}

export function AnswerCard({ answer, onFollowUp, disabled = false, showFollowUps = true }: Props) {
  const kpis = answer.panels.filter((p) => p.type === 'kpi')
  const others = answer.panels.filter((p) => p.type !== 'kpi')

  return (
    <article className="message message--assistant" aria-label={answer.title}>
      <div className="message__avatar">
        <SparkIcon />
      </div>
      <div className="answer">
        <h3>{answer.title}</h3>

        {answer.error && <p className="notice notice--warn">{answer.error}</p>}

        {answer.summary.length > 0 && (
          <ul className="answer__summary">
            {answer.summary.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}

        {kpis.length > 0 && (
          <section aria-label="Key figures" className="dashboard__kpis">
            {kpis.map((panel) => (
              <PanelView key={panel.id} panel={panel} currency={answer.currency} />
            ))}
          </section>
        )}

        {others.length > 0 && (
          <div className="dashboard__grid">
            {others.map((panel) => (
              <PanelView key={panel.id} panel={panel} currency={answer.currency} />
            ))}
          </div>
        )}

        {answer.failed_steps.length > 0 && (
          <div className="notice notice--warn">
            {answer.failed_steps.map((step, i) => (
              <p key={i}>{`Could not answer "${step.question}" — ${step.error}`}</p>
            ))}
          </div>
        )}

        {showFollowUps && answer.follow_ups.length > 0 && (
          <div className="answer__follow-ups">
            {answer.follow_ups.map((q) => (
              <button key={q} type="button" className="chip" onClick={() => onFollowUp(q)} disabled={disabled}>
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}
