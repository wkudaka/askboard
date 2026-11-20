import { ApiStatus } from './components/ApiStatus'

export default function App() {
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
      </main>
    </div>
  )
}
