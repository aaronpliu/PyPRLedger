/// <reference types="vite/client" />

// A .vue file is a module only Vue's own tooling can read, and that is what builds
// and type-checks the project. An editor whose TypeScript is not Vue-aware resolves
// nothing for an import of one and reports it as missing, so the shape is declared
// here as well: a tool that does resolve the file - vue-tsc, the build - uses the
// real component and never this, and one that does not has something to fall back on.
declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_WS_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
