import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { applyUiScale, loadUiScale } from './lib/uiScale'

// 在首次渲染前应用已保存的界面字号，避免闪烁。
applyUiScale(loadUiScale())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
