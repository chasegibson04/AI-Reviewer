#!/usr/bin/env node

import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(__dirname, '..')
const repoRoot = join(projectRoot, '..')
const legacyGuidedLauncher = join(repoRoot, 'launchers', 'launch_ai_reviewer.sh')
const runtimeConfigHome = join(projectRoot, '.runtime', '.claude')
const runtimeGlobalConfigFile = join(runtimeConfigHome, '.claude.json')
const srcRoot = join(projectRoot, 'src')
const distCli = join(projectRoot, 'dist', 'cli.mjs')
const userArgs = process.argv.slice(2)
const wantsLaunchPlan = userArgs.includes('--print-launch-plan')
const userArgsWithoutLaunchPlan = userArgs.filter(arg => arg !== '--print-launch-plan')
const hasBareFlag = userArgsWithoutLaunchPlan.includes('--bare')
const hasNoBareFlag = userArgsWithoutLaunchPlan.includes('--no-bare')
const passthroughArgs =
  hasBareFlag || hasNoBareFlag ? userArgsWithoutLaunchPlan : ['--bare', ...userArgsWithoutLaunchPlan]

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

function ensureRuntimeConfigHome() {
  // Keep runtime config self-contained for claude-review-v2 launches.
  // This avoids hidden coupling to user-global Claude config and prevents
  // trust-dialog dead-ends in this packaged launcher.
  process.env.CLAUDE_CONFIG_DIR = runtimeConfigHome
  mkdirSync(runtimeConfigHome, { recursive: true })

  let parsed = {}
  try {
    if (existsSync(runtimeGlobalConfigFile)) {
      parsed = JSON.parse(readFileSync(runtimeGlobalConfigFile, 'utf8'))
    }
  } catch {
    parsed = {}
  }

  const projects = {
    ...((parsed && typeof parsed === 'object' && parsed.projects && typeof parsed.projects === 'object')
      ? parsed.projects
      : {}),
    [projectRoot]: {
      ...((parsed && typeof parsed === 'object' && parsed.projects && parsed.projects[projectRoot] && typeof parsed.projects[projectRoot] === 'object')
        ? parsed.projects[projectRoot]
        : {}),
      hasTrustDialogAccepted: true,
    },
  }

  const merged = {
    ...(parsed && typeof parsed === 'object' ? parsed : {}),
    projects,
  }
  writeFileSync(runtimeGlobalConfigFile, JSON.stringify(merged, null, 2) + '\n', 'utf8')
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
  // Bun runtime can be enabled explicitly, but Node remains the default
  // runtime because Bun TTY streams are unstable in some terminal setups.
  if (process.env.CLAUDE_REVIEW_USE_BUN_RUNTIME === '1' && hasBun()) {
    return runCommand('bun', [distCli, ...passthroughArgs])
  }
  return runCommand(process.execPath, [distCli, ...passthroughArgs])
}

function launchLineRepl() {
  return runCommand(process.execPath, [join(projectRoot, 'scripts', 'line-repl.js')])
}

function hasLegacyGuidedLauncher() {
  return existsSync(legacyGuidedLauncher)
}

function launchLegacyGuidedWorkflow() {
  // Delegate to the existing AI-Reviewer guided workflow so users get
  // the exact project/workflow/profile/model menu and native run outputs.
  return runCommand('/bin/bash', [legacyGuidedLauncher, repoRoot])
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

  if (shouldUseLineRepl) {
    process.exit(launchLineRepl())
  }
  process.exit(launchDist())
}

const distHealth = getDistHealth()
ensureRuntimeConfigHome()

const shouldUseLegacyGuidedWorkflow =
  userArgsWithoutLaunchPlan.length === 0 &&
  process.env.CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED === '1' &&
  process.env.CLAUDE_REVIEW_USE_INTERNAL_LINE_REPL !== '1' &&
  hasLegacyGuidedLauncher()

const shouldUseLineRepl = userArgsWithoutLaunchPlan.length === 0 && !shouldUseLegacyGuidedWorkflow

if (wantsLaunchPlan) {
  const launchTarget = shouldUseLegacyGuidedWorkflow
    ? 'legacy_guided_workflow'
    : shouldUseLineRepl
      ? 'line_repl'
      : 'dist_cli'
  const payload = {
    launchTarget,
    projectRoot,
    distCliExists: distHealth.exists,
    distStale: distHealth.stale,
    distKnownBroken: distHealth.hasKnownBrokenBundleSignature,
    legacyGuidedAvailable: hasLegacyGuidedLauncher(),
    legacyGuidedEnabled: process.env.CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED === '1',
  }
  console.log(JSON.stringify(payload, null, 2))
  process.exit(0)
}

if (shouldUseLegacyGuidedWorkflow) {
  process.exit(launchLegacyGuidedWorkflow())
}

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

if (shouldUseLineRepl) {
  process.exit(launchLineRepl())
}

const firstLaunchStatus = launchDist()
if (firstLaunchStatus !== 0 && hasBun()) {
  console.error('claude-review-v2 launch detected a runtime failure; rebuilding once before retry.')
  buildAndLaunch()
}

process.exit(firstLaunchStatus)
