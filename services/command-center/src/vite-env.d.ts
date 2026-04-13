/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Empty = same-origin /api (recommended with dev proxy or reverse proxy). */
  readonly VITE_CONTROL_PLANE_URL?: string;
  readonly VITE_VOICE_SERVER_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
