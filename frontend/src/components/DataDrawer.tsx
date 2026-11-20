import { useEffect, useRef } from 'react'
import { DatasetList } from './DatasetList'
import { DatasetUpload } from './DatasetUpload'
import { CloseIcon } from './icons'
import { RelationshipList } from './RelationshipList'

interface Props {
  workspaceId: string
  open: boolean
  onClose: () => void
}

/**
 * Upload, datasets and relationships, in a panel over the chat.
 * Stays mounted while closed so a CSV under review is not lost.
 */
export function DataDrawer({ workspaceId, open, onClose }: Props) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    panel.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <div className="drawer" hidden={!open}>
      <div className="drawer__backdrop" onClick={onClose} />
      <div ref={panel} className="drawer__panel" role="dialog" aria-modal="true" aria-label="Data" tabIndex={-1}>
        <header className="drawer__header">
          <h2>Data</h2>
          <button type="button" className="icon-button" aria-label="Close data panel" onClick={onClose}>
            <CloseIcon />
          </button>
        </header>
        <div className="drawer__body">
          <section>
            <h3>Upload CSV</h3>
            <DatasetUpload workspaceId={workspaceId} />
          </section>
          <section>
            <h3>Datasets</h3>
            <DatasetList workspaceId={workspaceId} />
          </section>
          <section>
            <h3>Relationships</h3>
            <RelationshipList workspaceId={workspaceId} />
          </section>
        </div>
      </div>
    </div>
  )
}
