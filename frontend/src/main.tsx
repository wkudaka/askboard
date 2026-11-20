import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { ApiProvider } from './api/ApiProvider.tsx'
import { createApiClient } from './api/client.ts'
import './index.css'

const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
})
const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ApiProvider client={api}>
        <App />
      </ApiProvider>
    </QueryClientProvider>
  </StrictMode>,
)
