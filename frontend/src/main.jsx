import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Both routes render the same shell; App reads :id from the URL. */}
        <Route path="/" element={<App />} />
        <Route path="/chat/:id" element={<App />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
