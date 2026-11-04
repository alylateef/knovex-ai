import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      bg: 'var(--color-bg)',
      sidebar: 'var(--color-sidebar)',
      surface: 'var(--color-surface)',
      panel: 'var(--color-surface)',
      elevated: 'var(--color-elevated)',
      line: 'var(--color-line)',
      ink: 'var(--color-ink)',
      secondary: 'var(--color-secondary)',
      muted: 'var(--color-muted)',
      mark: 'var(--color-mark)',
      'mark-hover': 'var(--color-mark-hover)',
      'mark-bg': 'var(--color-mark-bg)',
      danger: 'var(--color-danger)',
    },
    spacing: {
      '0':    '0px',
      '0.5':  '2px',
      '1':    '4px',
      '1.5':  '6px',
      '2':    '8px',
      '2.5':  '10px',
      '3':    '12px',
      '3.5':  '14px',
      '4':    '16px',
      '5':    '24px',
      '6':    '32px',
      '7':    '48px',
      '8':    '64px',
    },
    fontSize: {
      xs:   ['12px', '16px'],
      sm:   ['14px', '20px'],
      base: ['16px', '24px'],
      lg:   ['19px', '33.25px'],  // Spectral answer line-height 1.75
      xl:   ['24px', '32px'],
      '2xl':['32px', '40px'],
    },
    borderRadius: {
      none:   '0px',
      sm:     '2px',
      input:  '4px',
      chip:   '3px',
      button: '6px',
      md:     '6px',
      lg:     '8px',
      xl:     '12px',
      '2xl':  '16px',
      full:   '9999px',
      panel:  '0px',
    },
    fontFamily: {
      sans:  ['"Schibsted Grotesk"', 'sans-serif'],
      serif: ['"Spectral"', 'serif'],
      mono:  ['"JetBrains Mono"', 'monospace'],
    },
    extend: {
      width: {
        shelf:  '250px',
        source: '370px',
      },
      maxWidth: {
        prose:    '46rem',
        ellipsis: '200px',
      },
      height: {
        px: '1px',
      },
      minWidth: {
        '0': '0px',
      },
      transitionDuration: {
        DEFAULT:   '150ms',
        inspector: '150ms',
      },
      scale: {
        '110': '1.1',
      },
      opacity: {
        '40': '0.4',
        '50': '0.5',
        '60': '0.6',
        '65': '0.65',
        '70': '0.7',
        '80': '0.8',
        '90': '0.9',
        '100': '1',
      },
      zIndex: {
        '20': '20',
        '30': '30',
      },
    },
  },
  plugins: [],
};

export default config;
