import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
    watch: {
      // Windows: cargo locks DLLs under src-tauri/target during first compile.
      // Watching them crashes Vite with EBUSY and aborts beforeDevCommand.
      ignored: ["**/src-tauri/**", "**/target/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
})
