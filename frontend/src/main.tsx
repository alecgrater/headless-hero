import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import ToastContainer from './components/ToastContainer.tsx'

createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <App />
    <ToastContainer />
  </ErrorBoundary>,
)
