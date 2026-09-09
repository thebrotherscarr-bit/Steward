// gm.ts — golden-master harness (catalog T4, SPEC_SEAM, ACCEPTANCE Gx-01).
// Orchestrates cutter --verify + consumer test batteries per stone.
// Node stdlib only, zero dependencies by standing law.
//
// atl gm run --stone <S>   — prove one stone
// atl gm run --prove       — prove all stones
// atl gm list              — list available stones

import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.dirname(HERE);
const PYTHON = process.platform === "win32" ? "python" : "python3";

// --- types -------------------------------------------------------------------

interface Stroke {
  name: string;
  ok: boolean;
  det: string;
}

interface StoneBattery {
  name: string;
  cutters: string[];     // Python cutter scripts (relative to repo/tools/)
  rust: string[];         // cargo test commands
  go: string[];           // go test commands
  ts: string[];           // TS/atl commands
}

interface StoneReport {
  stone: string;
  name: string;
  strokes: Array<{ pair: string; match: boolean; detail: string }>;
  mismatches: number;
}

// --- stone registry ----------------------------------------------------------

const STONES: Record<string, StoneBattery> = {
  A1: {
    name: "Spine",
    cutters: [
      "cut_canon_vectors.py",
      "cut_chain_verdicts.py",
      "cut_us_vectors.py",
    ],
    rust: [
      "cargo test -p atlas-core canon",
      "cargo test -p atlas-core chain",
      "cargo test -p atlas-core us_parity",
      "cargo test -p atlas-core covenant_golden",
      "cargo test -p atlas-store import_export",
    ],
    go: [],
    ts: [],
  },
  B1: {
    name: "THE LINE",
    cutters: [],
    rust: [],
    go: ["go test ./..."],
    ts: [],
  },
  C1: {
    name: "Faces",
    cutters: ["cut_faces_vectors.py"],
    rust: [],
    go: [],
    ts: [`${path.join("atl", "cli.ts")} self-test`],
  },
  D1: {
    name: "Town",
    cutters: ["cut_town_vectors.py"],
    rust: [],
    go: [
      "go test ./internal/town/...",
      "go test ./cmd/atlas-town/...",
    ],
    ts: [],
  },
  D2: {
    name: "Trade+Door",
    cutters: ["cut_trade_vectors.py"],
    rust: ["cargo test -p atlas-store trade_parity"],
    go: ["go test ./cmd/atlas-door/..."],
    ts: [],
  },
  E1: {
    name: "Kernels",
    cutters: [
      "cut_ppmi_vectors.py",
      "cut_digest_vectors.py",
      "cut_predict_vectors.py",
    ],
    rust: [],
    go: [],
    ts: [],
  },
  F1: {
    name: "Harvest",
    cutters: [
      "cut_rack_vectors.py",
      "cut_rack_ask_vectors.py",
      "cut_rack_open_vectors.py",
      "cut_memory_vectors.py",
      "cut_guard_vectors.py",
      "cut_skill_vectors.py",
    ],
    rust: [],
    go: ["go test ./..."],
    ts: [`${path.join("atl", "cli.ts")} self-test`],
  },
};

// --- runners -----------------------------------------------------------------

function runCmd(
  cmd: string,
  args: string[],
  opts: { cwd?: string; timeout?: number; shell?: boolean } = {},
): { ok: boolean; detail: string } {
  const r = spawnSync(cmd, args, {
    encoding: "utf-8",
    timeout: opts.timeout ?? 120_000,
    cwd: opts.cwd ?? REPO,
    stdio: ["pipe", "pipe", "pipe"],
    shell: opts.shell ?? false,
  });
  if (r.error) {
    return { ok: false, detail: `spawn error: ${String(r.error)}` };
  }
  const status = r.status ?? 1;
  const stderr = (r.stderr ?? "").trim();
  const stdout = (r.stdout ?? "").trim();
  if (status === 0) {
    return { ok: true, detail: stdout.split("\n")[0] ?? "ok" };
  }
  return {
    ok: false,
    detail: `exit ${status}${stderr ? ": " + stderr.split("\n")[0] : ""}`,
  };
}

function runCutter(script: string): { ok: boolean; detail: string } {
  const scriptPath = path.join(REPO, "tools", script);
  if (!fs.existsSync(scriptPath)) {
    return { ok: false, detail: `script not found: tools/${script}` };
  }
  // shell:true needed on Windows to resolve `python`
  return runCmd(PYTHON, [scriptPath, "--verify"], { timeout: 60_000, shell: true });
}

function runCargo(args: string): { ok: boolean; detail: string } {
  const parts = args.split(/\s+/);
  // No shell needed — cargo is a native executable on PATH
  return runCmd(parts[0], parts.slice(1));
}

function runGo(args: string): { ok: boolean; detail: string } {
  const parts = args.split(/\s+/);
  // Go tests must run from the line/ directory (the Go module root)
  return runCmd(parts[0], parts.slice(1), { cwd: path.join(REPO, "line") });
}

function runTs(args: string): { ok: boolean; detail: string } {
  // args is like "atl/cli.ts self-test" — run via node --experimental-strip-types
  const parts = args.split(/\s+/);
  const script = parts[0];
  const rest = parts.slice(1);
  const scriptPath = path.join(REPO, script);
  return runCmd(process.execPath, ["--experimental-strip-types", scriptPath, ...rest], {
    timeout: 120_000,
  });
}

// --- stone runner ------------------------------------------------------------

function runStone(key: string): StoneReport {
  const battery = STONES[key];
  if (!battery) {
    return {
      stone: key,
      name: "UNKNOWN",
      strokes: [{ pair: `stone ${key}`, match: false, detail: "unknown stone" }],
      mismatches: 1,
    };
  }

  const strokes: StoneReport["strokes"] = [];

  // Run cutters
  for (const c of battery.cutters) {
    const r = runCutter(c);
    strokes.push({ pair: `${c} --verify`, match: r.ok, detail: r.detail });
  }

  // Run Rust tests
  for (const cmd of battery.rust) {
    const r = runCargo(cmd);
    strokes.push({ pair: cmd, match: r.ok, detail: r.detail });
  }

  // Run Go tests
  for (const cmd of battery.go) {
    const r = runGo(cmd);
    strokes.push({ pair: cmd, match: r.ok, detail: r.detail });
  }

  // Run TS commands
  for (const cmd of battery.ts) {
    const r = runTs(cmd);
    strokes.push({ pair: cmd, match: r.ok, detail: r.detail });
  }

  const mismatches = strokes.filter((s) => !s.match).length;
  return { stone: key, name: battery.name, strokes, mismatches };
}

// --- public API --------------------------------------------------------------

export function gmList(): void {
  console.log("\n  Available stones:\n");
  for (const [key, bat] of Object.entries(STONES)) {
    const parts = [
      ...bat.cutters.map((c) => `cutter:${c}`),
      ...bat.rust.map((r) => `rust:${r}`),
      ...bat.go.map((g) => `go:${g}`),
      ...bat.ts.map((t) => `ts:${t}`),
    ];
    console.log(`    ${key}  ${bat.name}  (${parts.length} batteries)`);
  }
  console.log();
}

export function gmRun(stone?: string): number {
  const keys = stone ? [stone] : Object.keys(STONES);
  const reports: StoneReport[] = [];

  console.log("\n  ATL gm -- golden-master prove (hermetic)\n");

  for (const key of keys) {
    const report = runStone(key);
    reports.push(report);

    const tag = report.mismatches === 0 ? "PASS" : "FAIL";
    console.log(`  [${tag}]  ${report.stone} — ${report.name} (${report.strokes.length} strokes)`);
    for (const s of report.strokes) {
      const sTag = s.match ? "  PASS" : "  FAIL";
      console.log(`      ${sTag}  ${s.pair}  ${s.detail}`);
    }
  }

  const total = reports.reduce((a, r) => a + r.strokes.length, 0);
  const passed = reports.reduce((a, r) => a + r.strokes.filter((s) => s.match).length, 0);
  const failed = reports.reduce((a, r) => a + r.mismatches, 0);

  if (failed === 0) {
    console.log(`\n  PROVEN. ${passed}/${total} strokes green across ${reports.length} stone(s).\n`);
    return 0;
  } else {
    console.log(
      `\n  ${failed} stroke(s) failed (${passed}/${total} green) across ${reports.length} stone(s).\n`,
    );
    return 1;
  }
}

// --- JSON report (SPEC_SEAM format) ------------------------------------------

export function gmRunJson(stone?: string): StoneReport[] {
  const keys = stone ? [stone] : Object.keys(STONES);
  return keys.map(runStone);
}
