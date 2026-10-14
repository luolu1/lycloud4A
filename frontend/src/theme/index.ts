import { theme as antdTheme } from 'antd'
import type { ThemeConfig } from 'antd'

export type ThemeMode = 'light' | 'dark'

/** 品牌主色 + 科技青强调色 */
export const BRAND = {
  primary: '#1f3a93',
  primaryDark: '#5b8cff',
  accent: '#22d3ee',
} as const

export const FONT_SANS =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif"

export const FONT_MONO =
  "ui-monospace, 'JetBrains Mono', 'Cascadia Code', Consolas, Monaco, 'Courier New', monospace"

export const THEME_STORAGE_KEY = 'lycloud4a-theme'

/** recharts 等需要显式颜色的场景使用 */
export function chartPalette(mode: ThemeMode) {
  const dark = mode === 'dark'
  return {
    series: dark
      ? ['#5b8cff', '#22d3ee', '#7c5cff', '#3ddc97', '#f7b955', '#ff7875', '#b37feb']
      : ['#1f3a93', '#0e7490', '#6d28d9', '#16a34a', '#d97706', '#dc2626', '#7c3aed'],
    line: dark ? '#5b8cff' : '#1f3a93',
    bar: dark ? '#22d3ee' : '#2b5876',
    grid: dark ? 'rgba(150,170,215,0.14)' : 'rgba(16,24,40,0.08)',
    axis: dark ? '#8b98b4' : '#5b6675',
    tooltipBg: dark ? '#1a2138' : '#ffffff',
    tooltipBorder: dark ? '#2a3350' : '#e6eaf2',
    tooltipText: dark ? '#e6ebf5' : '#1f2733',
  }
}

/** 语义色（成功/警告/危险），随主题变化 */
export function semanticColors(mode: ThemeMode) {
  const dark = mode === 'dark'
  return {
    success: dark ? '#3ddc97' : '#16a34a',
    warning: dark ? '#f7b955' : '#d97706',
    danger: dark ? '#ff7875' : '#dc2626',
  }
}

export function buildTheme(mode: ThemeMode): ThemeConfig {
  const dark = mode === 'dark'
  const primary = dark ? BRAND.primaryDark : BRAND.primary

  return {
    algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: primary,
      colorInfo: primary,
      colorLink: primary,
      colorSuccess: dark ? '#3ddc97' : '#16a34a',
      colorWarning: dark ? '#f7b955' : '#d97706',
      colorError: dark ? '#ff7875' : '#dc2626',
      borderRadius: 8,
      borderRadiusLG: 12,
      controlHeight: 34,
      fontFamily: FONT_SANS,
      fontSize: 14,
      wireframe: false,
      colorBgLayout: dark ? '#0b1020' : '#f4f6fb',
      colorBgContainer: dark ? '#141a2e' : '#ffffff',
      colorBgElevated: dark ? '#1a2138' : '#ffffff',
      colorBorder: dark ? '#2a3350' : '#e6eaf2',
      colorBorderSecondary: dark ? '#202840' : '#eef1f7',
      colorText: dark ? '#e6ebf5' : '#1f2733',
      colorTextSecondary: dark ? '#98a2b8' : '#5b6675',
      boxShadow: dark
        ? '0 1px 2px rgba(0,0,0,.45), 0 8px 24px rgba(0,0,0,.35)'
        : '0 1px 2px rgba(16,24,40,.04), 0 8px 24px rgba(16,24,40,.06)',
      boxShadowSecondary: dark
        ? '0 6px 16px rgba(0,0,0,.45)'
        : '0 6px 16px rgba(16,24,40,.08)',
    },
    components: {
      Layout: {
        headerBg: 'transparent',
        bodyBg: 'transparent',
        siderBg: 'transparent',
        headerHeight: 62,
        headerPadding: '0 24px',
      },
      Menu: {
        darkItemBg: 'transparent',
        darkSubMenuItemBg: 'transparent',
        darkItemColor: 'rgba(226,233,247,.70)',
        darkItemHoverColor: '#ffffff',
        darkItemHoverBg: 'rgba(91,140,255,.14)',
        darkItemSelectedBg: 'rgba(34,211,238,.16)',
        darkItemSelectedColor: '#ffffff',
        itemBorderRadius: 8,
        itemMarginInline: 10,
        itemHeight: 42,
        itemMarginBlock: 4,
      },
      Card: {
        borderRadiusLG: 14,
        paddingLG: 20,
        headerFontSize: 15,
        headerHeight: 52,
      },
      Table: {
        headerBg: dark ? '#18203a' : '#f7f9fc',
        headerColor: dark ? '#a9b6d0' : '#41506a',
        headerSplitColor: 'transparent',
        borderColor: dark ? '#202840' : '#eef1f7',
        rowHoverBg: dark ? 'rgba(91,140,255,.07)' : '#f6f9ff',
        cellPaddingBlockSM: 10,
      },
      Button: { borderRadius: 8, controlHeight: 34, primaryShadow: 'none' },
      Tag: { borderRadiusSM: 6 },
      Modal: { borderRadiusLG: 14 },
      Input: { borderRadius: 8 },
      Tree: { nodeSelectedBg: dark ? 'rgba(34,211,238,.14)' : 'rgba(31,58,147,.08)' },
    },
  }
}
