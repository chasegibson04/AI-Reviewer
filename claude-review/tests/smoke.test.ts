import { test, describe } from "node:test";
import assert from "node:assert";
import { spawnSync } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CLI_PATH = path.resolve(__dirname, "../src/index.ts");

describe("Claude Review CLI Smoke Test", () => {
  test("--help should return help text", () => {
    const result = spawnSync("npx", ["tsx", CLI_PATH, "--help"], { encoding: "utf-8" });
    if (result.status !== 0) {
      console.error(result.stderr);
    }
    assert.ok(result.stdout.includes("Usage: claude-review [options] [command]"));
    assert.strictEqual(result.status, 0);
  });

  test("doctor should run basic checks", () => {
    const result = spawnSync("npx", ["tsx", CLI_PATH, "doctor"], { encoding: "utf-8" });
    assert.ok(result.stdout.includes("--- Claude Review Doctor ---"));
    assert.strictEqual(result.status, 0);
  });

  test("project-list should run without error", () => {
    const result = spawnSync("npx", ["tsx", CLI_PATH, "project-list"], { encoding: "utf-8" });
    assert.ok(result.stdout.includes("--- Projects ---"));
    assert.strictEqual(result.status, 0);
  });
});
