import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import App from './App'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider, useThemeMode } from './contexts/ThemeContext'
import { buildTheme } from './theme'
import './index.css'

dayjs.locale('zh-cn')

function Root() {
  const { mode } = useThemeMode()
  return (
    <ConfigProvider locale={zhCN} theme={buildTheme(mode)}>
      <AntApp>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <Root />
    </ThemeProvider>
  </React.StrictMode>,
)
