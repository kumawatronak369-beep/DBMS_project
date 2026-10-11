import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.jsx'],
    include: ['src/**/*.test.{js,jsx}'],
    css: false,
    testTimeout: 20000,
    maxWorkers: 6,
    clearMocks: true,
    unstubGlobals: true,
  },
})
