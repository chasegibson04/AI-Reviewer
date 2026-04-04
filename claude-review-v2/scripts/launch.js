#!/usr/bin/env node

import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(__dirname, '..')
const distCli = join(projectRoot, 'dist', 'cli.mjs')
const passthroughArgs = process.argv.slice(2)

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

if (existsSync(distCli)) {
  process.exit(launchDist())
}

if (!hasBun()) {
  console.error('claude-review-v2 launch failed: dist/cli.mjs does not exist and Bun is not installed.')
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
