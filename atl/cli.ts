// atl — the atlas toolchain (C1-03). Wraps the atlas binary, the faces,
// and the bridge. Node stdlib only, zero dependencies by standing law.
//
// Every command names its ground; strangers get nothing. `atl self-test`
// (alias `atl --prove`) is the shipped prove battery: temp grounds only.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as http from "node:http";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { snapshotGround } from "../faces/bridge/bridge.ts";
import { gmList, gmRun } from "./gm.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.dirname(HERE);
const FACES = path.join(REPO, "faces", "console-v2");

type Step = { name: string; ok: boolean; det: string };
const steps: Step[] = [];
function check(name: string, ok: boolean, det = ""): void {
  steps.push({ name, ok, det });
  console.log(`    [${ok ? "PASS" : "FAIL"}]  ${name}   ${det}`);
}

function repoVersion(): string {
  return fs.readFileSync(path.join(REPO, "VERSION"), "utf-8").trim();
}

function findAtlasBin(explicit = ""): string {
  if (explicit) return explicit;
  if (process.env.ATLAS_BIN) return String(process.env.ATLAS_BIN);
  const local = path.join(REPO, "target", "debug", process.platform === "win32" ? "atlas.exe" : "atlas");
  if (fs.existsSync(local)) return local;
  return "atlas";
}

function forwardAtlas(bin: string, args: string[]): number {
  const r = spawnSync(bin, args, { stdio: "inherit" });
  if (r.error) {
    console.error(`atl: cannot reach atlas binary ${bin}: ${String(r.error)}`);
    return 127;
  }
  return r.status ?? 1;
}

function flag(args: string[], name: string): string {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : "";
}

// --- faces serve ------------------------------------------------------------
const FLAG_NAME = /^[a-z0-9-]+$/;

export function faceBytes(root: string, flags: string[]): { body: Buffer; type: string } {
  const consoleHtml = fs.readFileSync(path.join(root, "console.html"));
  if (!flags.length) return { body: consoleHtml, type: "text/html; charset=utf-8" };
  const inject = `<script src="flags.js"></script><script>window.ATLAS_FLAGS=${JSON.stringify(flags)};</script>`;
  const html = String(consoleHtml).replace("</body>", inject + "</body>");
  return { body: Buffer.from(html, "utf-8"), type: "text/html; charset=utf-8" };
}

export function serveFaces(root: string, port: number): Promise<http.Server> {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const url = new URL(req.url ?? "/", "http://127.0.0.1");
      const p = url.pathname;
      try {
        if (p === "/" || p === "/console.html") {
          const flags = (url.searchParams.get("flags") ?? "").split(",").filter(Boolean);
          const { body, type } = faceBytes(root, flags);
          res.writeHead(200, { "content-type": type });
          res.end(body);
        } else if (p === "/sprites.js" || p === "/flags.js" || p === "/MANIFEST.json") {
          const f = path.join(root, p.slice(1));
          res.writeHead(200, { "content-type": p.endsWith(".json") ? "application/json" : "text/javascript; charset=utf-8" });
          res.end(fs.readFileSync(f));
        } else if (p.startsWith("/modules/")) {
          const name = p.slice("/modules/".length);
          if (!FLAG_NAME.test(name.replace(/\.js$/, "")) || name.includes("..") || !name.endsWith(".js")) {
            res.writeHead(403); res.end("refused: module names, never paths");
            return;
          }
          res.writeHead(200, { "content-type": "text/javascript; charset=utf-8" });
          res.end(fs.readFileSync(path.join(root, "modules", path.basename(name))));
        } else {
          res.writeHead(404); res.end("no such face");
        }
      } catch (e) {
        res.writeHead(404); res.end("no such face");
      }
    });
    // Loopback only: the face never binds outward. Zero egress by construction.
    srv.listen(port, "127.0.0.1", () => resolve(srv));
  });
}

function get(port: number, target: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    http.get({ host: "127.0.0.1", port, path: target }, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => chunks.push(c));
      res.on("end", () => resolve(Buffer.concat(chunks)));
    }).on("error", reject);
  });
}

// --- lint -------------------------------------------------------------------
// Patterns are built from strings (never regex literals) so the rules do
// not trip over their own spellings, and loopback is exempt: 127.0.0.1 is
// the face's own doorstep, not a remote.
const LINT_PATTERNS: Array<{ re: RegExp; why: string }> = [
  { re: new RegExp("https?://(?!127\\.0\\.0\\.1|localhost)"), why: "remote reference (faces are self-contained)" },
  { re: new RegExp("\\beval\\s*\\("), why: "dynamic code evaluation (never)" },
  { re: new RegExp("new Function\\s*\\("), why: "constructor call (never)" },
  { re: new RegExp("<script\\s+src=\"http"), why: "remote script (never)" },
];

export function lintTree(root: string, vendored: Set<string>): string[] {
  // Machine dirs and oracle bytes are not authored faces: .venv/node_modules/
  // target/.git are tooling, tests/fixtures are cutter-pinned oracle data
  // (their cutters, not lint, hold them). Everything else must be
  // self-contained: no remotes, no eval.
  const SKIP = new Set([".venv", "node_modules", "target", ".git", "fixtures"]);
  const SKIP_FILES = new Set(["package-lock.json"]); // npm's ledger, not authored source
  const hits: string[] = [];
  const walk = (dir: string): void => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const fp = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (!SKIP.has(e.name)) walk(fp);
        continue;
      }
      if (!/\.(ts|js|html|json)$/.test(e.name)) continue;
      if (SKIP_FILES.has(e.name)) continue;
      if (vendored.has(path.resolve(fp))) continue; // pinned bytes, checked by faces check
      const lines = fs.readFileSync(fp, "utf-8").split("\n");
      lines.forEach((ln, i) => {
        for (const p of LINT_PATTERNS) {
          if (p.re.test(ln)) hits.push(`${fp}:${i + 1}: ${p.why}`);
        }
      });
    }
  };
  walk(root);
  return hits;
}

function vendoredSet(): Set<string> {
  const man = JSON.parse(fs.readFileSync(path.join(FACES, "MANIFEST.json"), "utf-8")) as {
    console: { file: string }; sprites: { file: string };
  };
  return new Set([path.resolve(path.join(FACES, man.console.file)), path.resolve(path.join(FACES, man.sprites.file))]);
}

// --- faces check ------------------------------------------------------------
export function facesCheck(root: string): string[] {
  const fails: string[] = [];
  const man = JSON.parse(fs.readFileSync(path.join(root, "MANIFEST.json"), "utf-8")) as {
    console: { file: string; sha256: string; bytes: number };
    sprites: { file: string; sha256: string; bytes: number };
  };
  for (const entry of [man.console, man.sprites]) {
    const fp = path.join(root, entry.file);
    let body: Buffer;
    try {
      body = fs.readFileSync(fp);
    } catch {
      fails.push(`${entry.file}: absent`);
      continue;
    }
    if (createHash("sha256").update(body).digest("hex") !== entry.sha256) {
      fails.push(`${entry.file}: bytes drifted from the oracle pin`);
    }
    if (body.length !== entry.bytes) fails.push(`${entry.file}: size drifted`);
  }
  return fails;
}

// --- self-test --------------------------------------------------------------
async function selfTest(atlasBin: string): Promise<number> {
  console.log("\n  ATL -- self-test (hermetic; temp grounds only)");
  const vers = repoVersion();
  check("version pinned", /^\d+\.\d+\.\d+\+\w+$/.test(vers), vers);
  // Cross-file consistency: every VERSION copy agrees (catches partial bumps).
  const lineVers = fs.readFileSync(path.join(REPO, "line", "VERSION"), "utf-8").trim();
  check("VERSION agrees across root and line", lineVers === vers, `root=${vers} line=${lineVers}`);
  const mcpVers = fs.readFileSync(path.join(REPO, "line", "cmd", "atlas-mcp", "VERSION"), "utf-8").trim();
  const townVers = fs.readFileSync(path.join(REPO, "line", "cmd", "atlas-town", "VERSION"), "utf-8").trim();
  const doorVers = fs.readFileSync(path.join(REPO, "line", "cmd", "atlas-door", "VERSION"), "utf-8").trim();
  check("VERSION agrees across all binaries", mcpVers === vers && townVers === vers && doorVers === vers,
    `mcp=${mcpVers} town=${townVers} door=${doorVers}`);

  // 1. faces check: vendored bytes == oracle pins.
  const fc = facesCheck(FACES);
  check("faces check: console+sprites match the oracle pins", fc.length === 0, fc.join("; "));

  // 2. bridge golden: TS fold == cutter bytes.
  const goldenDir = path.join(REPO, "tests", "fixtures", "faces_ground");
  const goldenSnap = fs.readFileSync(path.join(REPO, "tests", "fixtures", "faces_snapshot.json"), "utf-8");
  let bridgeOk = false;
  try {
    bridgeOk = snapshotGround(goldenDir, "faces-golden") === goldenSnap;
  } catch (e) { /* stays false, named below */ }
  check("bridge snapshot reproduces the golden bytes", bridgeOk);

  // 3. bridge read-only, observed: ground bytes identical across a snapshot.
  const before = snapshotGround(goldenDir, "faces-golden");
  const after = snapshotGround(goldenDir, "faces-golden");
  check("bridge leaves the ground untouched", before === after && before === goldenSnap);

  // 4. serve: flags off = oracle bytes; flags on = additive only.
  const srv = await serveFaces(FACES, 0);
  const port = (srv.address() as { port: number }).port;
  try {
    const off = await get(port, "/");
    const oracle = fs.readFileSync(path.join(FACES, "console.html"));
    check("served flags-off face is the oracle bytes", off.equals(oracle));
    const on = await get(port, "/?flags=demo");
    check("served flags-on face adds the loader, keeps the body",
      !on.equals(oracle) && on.includes('src="flags.js"') && on.includes("the glass"));
  } finally {
    srv.close();
  }

  // 5. enroll parity: atl wraps atlas byte-for-byte (temp copy of the
  // seed db + self-contained operator<->manjuel pair, as the Rust tests do).
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "atl_selftest_"));
  try {
    const agdir = path.join(tmp, "agents");
    fs.mkdirSync(agdir);
    for (const f of ["operator.us", "manjuel.us"]) {
      fs.copyFileSync(path.join(REPO, "agents", f), path.join(agdir, f));
    }
    const db = path.join(tmp, "t.db");
    fs.copyFileSync(path.join(REPO, "data", "master.db"), db);
    const bin = findAtlasBin(atlasBin);
    const direct = spawnSync(bin, ["agent", "enroll", db, "--dir", agdir, "--dry"], { encoding: "utf-8" });
    const wrapped = spawnSync(process.execPath, [path.join(HERE, "cli.ts"), "agent", "enroll", "--db", db, "--dir", agdir, "--dry"], { encoding: "utf-8" });
    const same = direct.status === 0 && wrapped.status === 0 && direct.stdout === wrapped.stdout;
    check("atl agent enroll wraps atlas byte-for-byte", same, `direct=${direct.status} wrapped=${wrapped.status}`);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  // 6. lint clean over authored faces.
  const hits = lintTree(REPO, vendoredSet()).filter((h) => h.includes(`${path.sep}faces${path.sep}`) || h.includes(`${path.sep}atl${path.sep}`));
  check("lint clean over authored faces", hits.length === 0, hits.slice(0, 3).join("; "));

  // 7. skill lint reproduces the golden verdicts fixture by fixture.
  const skGold = JSON.parse(fs.readFileSync(
    path.join(REPO, "tests", "fixtures", "skill_vectors.json"), "utf-8")) as {
    cases: Array<{ dir: string; expect: string[] }>;
  };
  const skRows = lintSkills(path.join(REPO, "tests", "fixtures", "skills"));
  let skOk = skRows.length === skGold.cases.length;
  for (const c of skGold.cases) {
    const row = skRows.find((r) => r.dir === c.dir);
    if (!row || JSON.stringify(row.bad) !== JSON.stringify(c.expect)) skOk = false;
  }
  check("skill lint matches golden verdicts", skOk,
    skRows.map((r) => `${r.dir}:${r.bad.join("+") || "clean"}`).join(" "));

  const failed = steps.filter((s) => !s.ok);
  console.log(failed.length ? `\n  ${failed.length} step(s) failed. The toolchain is not yet what it claims.\n` : "\n  PROVEN. The toolchain wraps, serves, and folds.\n");
  return failed.length ? 1 : 0;
}

// --- skill lint (F1-03) --------------------------------------------------------
// Rules R1..R5, pinned by tests/fixtures/skill_vectors.json: frontmatter
// block; name present, shaped, == dirname; description 10..500 chars;
// headed non-empty body; no duplicate keys. Absence cascades honestly.
const SKILL_NAME = /^[a-z0-9-]+$/;

export function lintSkill(text: string, dirname: string): string[] {
  const bad: string[] = [];
  const lines = text.split("\n");
  const fm = new Map<string, string>();
  const dupes = new Set<string>();
  let body = text;
  if (lines.length < 2 || lines[0].trim() !== "---") {
    bad.push("R1");
  } else {
    let end = -1;
    for (let i = 1; i < lines.length; i++) {
      if (lines[i].trim() === "---" || lines[i].trim() === "...") { end = i; break; }
    }
    if (end < 0) {
      bad.push("R1");
    } else {
      // Folded scalars (>, | + chomping): following indented lines belong
      // to the value (standard frontmatter; the real rack uses them).
      const fmlines = lines.slice(1, end);
      let idx = 0;
      while (idx < fmlines.length) {
        const ln = fmlines[idx];
        if (!ln.trim() || ln.trim().startsWith("#") || !ln.includes(":")) { idx++; continue; }
        const parts = ln.split(":");
        const k = (parts[0] ?? "").trim();
        let v = parts.slice(1).join(":").trim();
        if (v === ">" || v === "|" || v === ">-" || v === ">+" || v === "|-" || v === "|+" ||
            v.startsWith("> ") || v.startsWith("| ")) {
          const style = v[0];
          const buf: string[] = [];
          idx++;
          while (idx < fmlines.length &&
                 (fmlines[idx].startsWith(" ") || fmlines[idx].startsWith("\t"))) {
            buf.push(fmlines[idx].trim());
            idx++;
          }
          v = style === ">" ? buf.join(" ") : buf.join("\n");
          if (fm.has(k)) dupes.add(k);
          fm.set(k, v);
          continue;
        }
        if (fm.has(k)) dupes.add(k);
        fm.set(k, v);
        idx++;
      }
      body = lines.slice(end + 1).join("\n");
    }
  }
  if (dupes.size) bad.push("R5");
  const name = fm.get("name") ?? "";
  if (!name || !SKILL_NAME.test(name) || name !== dirname) bad.push("R2");
  const desc = fm.get("description") ?? "";
  if (!(desc.length >= 10 && desc.length <= 500)) bad.push("R3");
  const blines = body.split("\n").filter((l) => l.trim());
  if (!(blines.some((l) => l.trim().startsWith("#")) &&
        blines.some((l) => !l.trim().startsWith("#")))) bad.push("R4");
  return [...new Set(bad)].sort();
}

export function lintSkills(dir: string): Array<{ dir: string; bad: string[] }> {
  const out: Array<{ dir: string; bad: string[] }> = [];
  let entries: string[] = [];
  try {
    entries = fs.readdirSync(dir);
  } catch {
    return out;
  }
  for (const e of entries.sort()) {
    const fp = path.join(dir, e, "SKILL.md");
    let text: string;
    try {
      text = fs.readFileSync(fp, "utf-8");
    } catch {
      continue;
    }
    out.push({ dir: e, bad: lintSkill(text, e) });
  }
  return out;
}

// --- main -------------------------------------------------------------------
function usage(): number {
  console.log(`atl ${repoVersion()} — the atlas toolchain
  atl agent enroll --db <db> --dir <agents> [--dry]   wrap atlas enrollment
  atl agent orient --home <dir>                        wrap atlas orientation
  atl bridge snapshot --ground <dir> [--name N]        fold a ground to JSON
  atl faces serve [--port 0]                           serve the face (loopback)
  atl faces check                                      vendored bytes vs oracle pins
  atl gm run [--stone <S>]                             golden-master prove (Gx-01)
  atl gm list                                          list available stones
  atl skill lint [--dir D]                             SKILL.md rules R1..R5 over a rack
  atl lint                                             scan authored tree (machine dirs + oracle fixtures exempt)
  atl self-test | atl --prove                          shipped prove battery
  atl --version                                        semver+stone`);
  return 2;
}

async function main(): Promise<number> {
  const args = process.argv.slice(2);
  const cmd = args[0] ?? "";
  if (cmd === "--version") { console.log(repoVersion()); return 0; }
  if (cmd === "--prove" || (cmd === "self-test")) return selfTest(flag(args, "--atlas-bin"));
  if (cmd === "agent" && args[1] === "enroll") {
    const db = flag(args, "--db"), dir = flag(args, "--dir");
    if (!db || !dir) { console.error("atl agent enroll --db <db> --dir <agents> [--dry]"); return 2; }
    const rest = ["agent", "enroll", db, "--dir", dir];
    if (args.includes("--dry")) rest.push("--dry");
    return forwardAtlas(findAtlasBin(flag(args, "--atlas-bin")), rest);
  }
  if (cmd === "agent" && args[1] === "orient") {
    const home = flag(args, "--home");
    if (!home) { console.error("atl agent orient --home <dir>"); return 2; }
    return forwardAtlas(findAtlasBin(flag(args, "--atlas-bin")), ["orient", "--home", home]);
  }
  if (cmd === "bridge" && args[1] === "snapshot") {
    const ground = flag(args, "--ground");
    if (!ground) { console.error("atl bridge snapshot --ground <dir> [--name N] [--out F]"); return 2; }
    const out = snapshotGround(ground, flag(args, "--name") || "live");
    const dest = flag(args, "--out");
    if (dest) fs.writeFileSync(dest, out);
    else process.stdout.write(out);
    return 0;
  }
  if (cmd === "faces" && args[1] === "serve") {
    const port = Number(flag(args, "--port") || "0");
    const srv = await serveFaces(FACES, Number.isInteger(port) ? port : 0);
    console.log(`face on loopback ${(srv.address() as { port: number }).port} (flags off = oracle bytes)`);
    await new Promise<never>(() => {});
    return 0;
  }
  if (cmd === "faces" && args[1] === "check") {
    const fails = facesCheck(FACES);
    fails.forEach((f) => console.log("  drift: " + f));
    console.log(fails.length ? "FACE DRIFTED" : "FACE HOLDS (oracle bytes)");
    return fails.length ? 1 : 0;
  }
  if (cmd === "lint") {
    const hits = lintTree(REPO, vendoredSet());
    hits.forEach((h) => console.log("  " + h));
    console.log(hits.length ? `LINT FAILED (${hits.length})` : "LINT CLEAN");
    return hits.length ? 1 : 0;
  }
  if (cmd === "skill" && args[1] === "lint") {
    const dir = flag(args, "--dir") ||
      path.join(REPO, "..", "estate", "Agent Skills", "rack");
    const rows = lintSkills(dir);
    if (!rows.length) {
      console.log(`no skills under ${dir} — nothing linted, nothing claimed.`);
      return 1;
    }
    let flagged = 0;
    for (const r of rows) {
      if (r.bad.length) {
        flagged++;
        console.log(`  ${r.dir}: ${r.bad.join(", ")}`);
      }
    }
    const clean = rows.length - flagged;
    console.log(clean && !flagged ? `SKILL LINT CLEAN (${clean})`
      : `SKILL LINT: ${clean} clean, ${flagged} flagged`);
    return flagged ? 1 : 0;
  }
  if (cmd === "gm") {
    const sub = args[1] ?? "";
    if (sub === "list") { gmList(); return 0; }
    if (sub === "run") {
      const stone = flag(args, "--stone");
      return gmRun(stone || undefined);
    }
    console.error("atl gm run [--stone <S>] | atl gm list");
    return 2;
  }
  return usage();
}

// node ESM: top-level await is erasable-safe.
await (async () => { process.exitCode = await main(); })();
