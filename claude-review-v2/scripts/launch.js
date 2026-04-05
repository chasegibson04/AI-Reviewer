#!/usr/bin/env node

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(__dirname, '..')
const srcRoot = join(projectRoot, 'src')
const distCli = join(projectRoot, 'dist', 'cli.mjs')
const passthroughArgs = process.argv.slice(2)

function newestMtimeRecursive(rootPath) {
  let newest = 0
  const stack = [rootPath]
  while (stack.length > 0) {
    const current = stack.pop()
    let entries
    try {
      entries = readdirSync(current, { withFileTypes: true })
    } catch {
      continue
    }
    for (const entry of entries) {
      const full = join(current, entry.name)
      if (entry.isDirectory()) {
        stack.push(full)
        continue
      }
      if (!entry.isFile()) continue
      try {
        const mtimeMs = statSync(full).mtimeMs
        if (mtimeMs > newest) newest = mtimeMs
      } catch {
        // ignore unreadable files
      }
    }
  }
  return newest
}

function getDistHealth() {
  if (!existsSync(distCli)) {
    return { exists: false, stale: true, hasKnownBrokenBundleSignature: false }
  }

  let distMtimeMs = 0
  try {
    distMtimeMs = statSync(distCli).mtimeMs
  } catch {
    distMtimeMs = 0
  }

  const srcNewestMtimeMs = newestMtimeRecursive(srcRoot)
  const scriptsNewestMtimeMs = newestMtimeRecursive(join(projectRoot, 'scripts'))
  const stale = distMtimeMs < Math.max(srcNewestMtimeMs, scriptsNewestMtimeMs)

  let hasKnownBrokenBundleSignature = false
  try {
    const distText = readFileSync(distCli, 'utf8')
    hasKnownBrokenBundleSignature =
      distText.includes('getGrowthBookClient = default169(') ||
      distText.includes('initializeGrowthBook = default169(')
  } catch {
    hasKnownBrokenBundleSignature = true
  }

  return { exists: true, stale, hasKnownBrokenBundleSignature }
}

function runCommand(command, args) {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    stdio: 'inherit',
    env: process.env,
  })
  return result.status ?? 1
}

function hasBun() {
  const result = spawnSync('bun', ['--version'], {
    cwd: projectRoot,
    stdio: 'ignore',
    env: process.env,
  })
  return (result.status ?? 1) === 0
}

function launchDist() {
  return runCommand(process.execPath, [distCli, ...passthroughArgs])
}

function buildAndLaunch() {
  const buildStatus = runCommand('bun', ['run', 'build'])
  if (buildStatus !== 0) {
    console.error('claude-review-v2 launch failed: build step did not complete.')
    console.error('Diagnostic commands:')
    console.error('  - bun run smoke')
    console.error('  - bash scripts/smoke_fallback.sh')
    process.exit(buildStatus)
  }

  if (!existsSync(distCli)) {
    console.error('claude-review-v2 launch failed: build finished but dist/cli.mjs is still missing.')
    process.exit(1)
  }

  process.exit(launchDist())
}

const distHealth = getDistHealth()

if (!distHealth.exists || distHealth.stale || distHealth.hasKnownBrokenBundleSignature) {
  if (!hasBun()) {
    console.error('claude-review-v2 launch failed: dist is missing/stale/broken and Bun is not installed.')
    console.error('')
    console.error('Recovery steps:')
    console.error('  1) Install Bun: https://bun.sh')
    console.error('  2) Build once: bun run build')
    console.error('  3) Relaunch from this script')
    console.error('')
    console.error('Diagnostic commands:')
    console.error('  - bash scripts/doctor_runtime.sh')
    console.error('  - bash scripts/smoke_fallback.sh')
    process.exit(1)
  }
  buildAndLaunch()
}

const firstLaunchStatus = launchDist()
if (firstLaunchStatus !== 0 && hasBun()) {
  console.error('claude-review-v2 launch detected a runtime failure; rebuilding once before retry.')
  buildAndLaunch()
}

process.exit(firstLaunchStatus)
