import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { Navigate, RouterProvider, createBrowserRouter, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource-variable/unbounded'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'
import './styles.css'
import { ApiError } from './lib/api'
import { AuthProvider, useAuth } from './lib/auth'
import { Shell } from './components/Shell'
import { Login } from './pages/Login'
import { Callback } from './pages/Callback'
import { Overview } from './pages/Overview'
import { Logs } from './pages/Logs'
import { LogDetailPage } from './pages/LogDetailPage'
import { Services } from './pages/Services'
import { System } from './pages/System'
import { NotFound } from './pages/NotFound'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      // Client errors (4xx) will not fix themselves on retry.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
})

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth()
  const location = useLocation()
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/auth/callback', element: <Callback /> },
  {
    element: (
      <RequireAuth>
        <Shell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Overview /> },
      { path: 'logs', element: <Logs /> },
      { path: 'logs/:logType/:logId', element: <LogDetailPage /> },
      { path: 'services', element: <Services /> },
      { path: 'system', element: <System /> },
      { path: 'dashboard', element: <Navigate to="/" replace /> },
      { path: 'health', element: <Navigate to="/system" replace /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
