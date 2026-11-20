import { useState } from 'react'
import { ApiStatus } from './components/ApiStatus'
import { DatasetList } from './components/DatasetList'
import { DatasetUpload } from './components/DatasetUpload'
import { WorkspacePicker } from './components/WorkspacePicker'

export default function App() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)

  return (
    <div className="app">
      <header className="app__header">
        <h1>Askboard</h1>
        <ApiStatus />
      </header>
      <main className="app__main">
        <p className="app__tagline">
          Upload your CSVs, ask questions in plain language, get a dashboard.
        </p>
        <WorkspacePicker value={workspaceId} onChange={setWorkspaceId} />
        {workspaceId && (
          <>
            <section className="card">
              <h2>Upload data</h2>
              <DatasetUpload key={workspaceId} workspaceId={workspaceId} />
            </section>
            <section className="card">
              <h2>Datasets</h2>
              <DatasetList workspaceId={workspaceId} />
            </section>
          </>
        )}
      </main>
    </div>
  )
}
