/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Empty = same-origin /api (recommended with dev proxy or reverse proxy). */
  readonly VITE_CONTROL_PLANE_URL?: string;
  readonly VITE_VOICE_SERVER_URL?: string;
  /** Runtime display (Slice C); align with JARVIS_LOCAL_MODEL / JARVIS_CLOUD_MODEL on workers. */
  readonly VITE_JARVIS_LOCAL_MODEL?: string;
  readonly VITE_JARVIS_CLOUD_MODEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
