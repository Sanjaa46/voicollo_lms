import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './services/authContext'
import { Login } from './pages/Login'
import { Callback } from './pages/Callback'
import { Dashboard } from './pages/Dashboard'
import { LogDetails } from './pages/LogDetails'
import { Health } from './pages/Health'
import { Services } from './pages/Services'
import { ProtectedRoute } from './components/ProtectedRoute'
import './index.css'

import { initializeApiClient } from './services/api';

initializeApiClient();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    }
  }
})

const router = createBrowserRouter([
  {
    path: '/',
    element: <Login />
  },
  {
    path: '/auth/callback',
    element: <Callback />
  },
  {
    path: '/dashboard',
    element: (
      <ProtectedRoute>
        <Dashboard />
      </ProtectedRoute>
    )
  },
  {
    path: '/logs/:logType/:logId',
    element: (
      <ProtectedRoute>
        <LogDetails />
      </ProtectedRoute>
    )
  },
  {
    path: '/health',
    element: (
      <ProtectedRoute>
        <Health />
      </ProtectedRoute>
    )
  },
  {
    path: '/services',
    element: (
      <ProtectedRoute>
        <Services />
      </ProtectedRoute>
    )
  }
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