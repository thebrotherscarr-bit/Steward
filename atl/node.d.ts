// node.d.ts — minimal ambient declarations for the node builtins atl uses.
//
// @types/node is an npm package, and npm is refused by standing law
// (zero external dependencies). So this file hand-rolls the exact surface
// atl touches — nothing more. If atl needs a new builtin, its shape lands
// here first, quoted from node's own docs, then gets used.
declare module "node:fs" {
  interface Dirent {
    name: string;
    isDirectory(): boolean;
    isFile(): boolean;
  }
  export function readFileSync(path: string, encoding: "utf-8"): string;
  export function readFileSync(path: string): Buffer;
  export function writeFileSync(path: string, data: string | Buffer): void;
  export function readdirSync(path: string, opts: { withFileTypes: true }): Dirent[];
  export function readdirSync(path: string): string[];
  export function existsSync(path: string): boolean;
  export function mkdirSync(path: string, opts?: { recursive?: boolean }): void;
  export function mkdtempSync(prefix: string): string;
  export function copyFileSync(src: string, dest: string): void;
  export function rmSync(path: string, opts?: { recursive?: boolean; force?: boolean }): void;
}

declare module "node:path" {
  export function join(...parts: string[]): string;
  export function dirname(p: string): string;
  export function basename(p: string, ext?: string): string;
  export function resolve(...parts: string[]): string;
  export const sep: string;
}

declare module "node:os" {
  export function tmpdir(): string;
}

declare module "node:url" {
  export function fileURLToPath(url: string): string;
}

declare module "node:crypto" {
  interface Hash {
    update(data: string | Buffer): Hash;
    digest(encoding: "hex"): string;
  }
  export function createHash(algo: string): Hash;
}

declare module "node:child_process" {
  interface SpawnResult {
    status: number | null;
    stdout: string;
    stderr: string;
    error?: Error;
  }
  export function spawnSync(
    cmd: string,
    args: string[],
    opts?: {
      stdio?: string | unknown[];
      encoding?: string;
      env?: Record<string, string | undefined>;
      shell?: boolean;
      cwd?: string;
      timeout?: number;
    },
  ): SpawnResult;
}

declare module "node:http" {
  interface IncomingMessage {
    url?: string;
    on(event: "data", cb: (chunk: Buffer) => void): void;
    on(event: "end", cb: () => void): void;
  }
  interface ServerResponse {
    writeHead(status: number, headers?: Record<string, string>): void;
    end(body?: string | Buffer): void;
  }
  interface AddressInfo {
    port: number;
    address: string;
  }
  interface Server {
    listen(port: number, host: string, cb?: () => void): void;
    address(): AddressInfo | null;
    close(cb?: () => void): void;
  }
  export function createServer(
    handler: (req: IncomingMessage, res: ServerResponse) => void,
  ): Server;
  export function get(
    opts: { host: string; port: number; path: string },
    cb: (res: IncomingMessage & { statusCode?: number }) => void,
  ): { on(event: string, cb: (e: Error) => void): void };
}

// Globals (lib has no DOM/node types by design here).
declare const process: {
  argv: string[];
  env: Record<string, string | undefined>;
  execPath: string;
  platform: string;
  exitCode: number;
  stdout: { write(s: string): void };
};
declare const Buffer: {
  from(s: string, encoding?: string): Buffer;
  concat(parts: Buffer[]): Buffer;
};
interface Buffer {
  length: number;
  equals(other: Buffer): boolean;
  includes(s: string | Buffer): boolean;
}
declare const console: {
  log(...args: string[]): void;
  error(...args: string[]): void;
  warn(...args: string[]): void;
};
declare const URL: {
  new (input: string, base?: string): {
    pathname: string;
    searchParams: { get(name: string): string | null };
  };
};
