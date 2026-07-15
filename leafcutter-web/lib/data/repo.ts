import "server-only";
import fs from "node:fs";
import path from "node:path";

/**
 * Resolve the leafcutter-ai repo root whose data the Atlas renders.
 *
 * Priority:
 *   1. LEAFCUTTER_REPO_ROOT env var (absolute path) — for pointing at any repo,
 *      the seam that lets this site host OTHER projects later.
 *   2. The parent of the Next.js app dir (process.cwd()/..) — the default when
 *      the site lives as a subdirectory inside the repo/worktree it documents.
 *
 * Verified by probing for docs/roadmap.json.
 */
export function repoRoot(): string {
  const env = process.env.LEAFCUTTER_REPO_ROOT;
  if (env && fs.existsSync(path.join(env, "docs", "roadmap.json"))) {
    return env;
  }
  const parent = path.resolve(process.cwd(), "..");
  if (fs.existsSync(path.join(parent, "docs", "roadmap.json"))) {
    return parent;
  }
  // Fall back to cwd (allows running from repo root directly).
  if (fs.existsSync(path.join(process.cwd(), "docs", "roadmap.json"))) {
    return process.cwd();
  }
  // Last resort: parent, so callers get a stable base even if probing failed.
  return parent;
}

/** Absolute path inside the repo. */
export function repoPath(...segments: string[]): string {
  return path.join(repoRoot(), ...segments);
}

/** Read a UTF-8 file, returning null on any I/O error (never throws). */
export function readFileSafe(abs: string): string | null {
  try {
    return fs.readFileSync(abs, "utf8");
  } catch {
    return null;
  }
}

/** Recursively collect files under `dir` matching `ext` (e.g. ".yaml"). */
export function walk(dir: string, ext: string): string[] {
  const out: string[] = [];
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...walk(full, ext));
    } else if (e.isFile() && e.name.endsWith(ext)) {
      out.push(full);
    }
  }
  return out;
}

/** Convert an absolute repo path to a repo-relative one. */
export function rel(abs: string): string {
  return path.relative(repoRoot(), abs).split(path.sep).join("/");
}
