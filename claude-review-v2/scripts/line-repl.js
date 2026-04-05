#!/usr/bin/env node

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, join, relative, resolve } from 'node:path'
import { spawn, spawnSync } from 'node:child_process'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(__dirname, '..')
const stateDir = join(projectRoot, '.runtime')
const stateFile = join(stateDir, 'interactive_state.json')
const bridgeScript = join(projectRoot, 'src', 'bridge', 'python', 'review_mcp_server.py')
const runRoot = join(projectRoot, 'test_outputs', 'interactive_runs')
const blockedProjectSnippets = ['pampa', 'horseshoe']

const profileCatalog = [
  { id: 'balanced_local', label: 'Balanced Local (stable local path)' },
  { id: 'deep_local', label: 'Deep Local (stronger multi-stage path)' },
  { id: 'local_moe', label: 'Local MOE (staged routing)' },
  { id: 'one_big_model', label: 'One Big Model (Gemma4 preferred)' },
  { id: 'full_manuscript_final_pass', label: 'Full Manuscript Final Pass (Gemma4 preferred)' },
  { id: 'offline_strict', label: 'Offline Strict' },
]

function isBlockedName(name) {
  const lower = String(name || '').toLowerCase()
  return blockedProjectSnippets.some(snippet => lower.includes(snippet))
}

function listProjectDirs() {
  const root = join(projectRoot, 'projects')
  if (!existsSync(root)) return []
  return readdirSync(root, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => join(root, d.name))
    .filter(p => !isBlockedName(p))
}

function defaultState() {
  const projects = listProjectDirs()
  const activeProjectDir = projects[0] || projectRoot
  return {
    activeProjectDir,
    activeProfile: 'local_moe',
    lastRunDir: null,
  }
}

function loadState() {
  try {
    if (!existsSync(stateFile)) return defaultState()
    const parsed = JSON.parse(readFileSync(stateFile, 'utf8'))
    const merged = { ...defaultState(), ...parsed }
    if (isBlockedName(merged.activeProjectDir)) {
      merged.activeProjectDir = defaultState().activeProjectDir
    }
    return merged
  } catch {
    return defaultState()
  }
}

function saveState(state) {
  mkdirSync(stateDir, { recursive: true })
  writeFileSync(stateFile, JSON.stringify(state, null, 2) + '\n', 'utf8')
}

function displayPath(absPath) {
  const rel = relative(projectRoot, absPath || projectRoot)
  return rel && rel.length > 0 ? rel : '.'
}

function modelInventory() {
  const res = spawnSync('ollama', ['list'], { encoding: 'utf8' })
  if ((res.status ?? 1) !== 0) return { ok: false, models: [] }
  const lines = (res.stdout || '').split(/\r?\n/).slice(1)
  const models = lines
    .map(line => line.trim().split(/\s+/)[0])
    .filter(Boolean)
  return { ok: true, models }
}

function pickModel(profileId, models) {
  const has = name => models.includes(name)
  if (profileId === 'one_big_model' || profileId === 'full_manuscript_final_pass') {
    if (has('gemma4:26b')) return 'gemma4:26b'
    if (has('gemma4:31b')) return 'gemma4:31b'
  }
  if (profileId === 'balanced_local') return has('llama3.1:8b') ? 'llama3.1:8b' : (models[0] || 'unknown')
  if (profileId === 'deep_local') return has('qwen2.5-coder:32b') ? 'qwen2.5-coder:32b' : (models[0] || 'unknown')
  if (profileId === 'local_moe') return 'local_moe'
  if (profileId === 'offline_strict') return models[0] || 'offline'
  return models[0] || 'unknown'
}

class BridgeClient {
  constructor(cwd) {
    this.cwd = cwd
    this.proc = null
    this.rl = null
    this.nextId = 1
    this.pending = new Map()
  }

  async start() {
    if (this.proc) return
    this.proc = spawn('python3', [bridgeScript], {
      cwd: projectRoot,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: process.env,
    })
    this.proc.stderr.on('data', chunk => {
      const msg = String(chunk || '').trim()
      if (msg) process.stderr.write(`[bridge] ${msg}\n`)
    })

    this.rl = readline.createInterface({ input: this.proc.stdout })
    this.rl.on('line', line => {
      let payload
      try {
        payload = JSON.parse(line)
      } catch {
        return
      }
      const id = payload.id
      if (!this.pending.has(id)) return
      const entry = this.pending.get(id)
      clearTimeout(entry.timeout)
      this.pending.delete(id)
      entry.resolve(payload)
    })

    await this.send('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'line-repl', version: '1.0.0' },
    })
  }

  async send(method, params) {
    await this.start()
    const id = this.nextId++
    const req = { jsonrpc: '2.0', id, method, params }
    return await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`Bridge timeout on ${method}`))
      }, 30000)
      this.pending.set(id, { resolve, reject, timeout })
      this.proc.stdin.write(JSON.stringify(req) + '\n')
    })
  }

  async callTool(name, argumentsObj) {
    const response = await this.send('tools/call', { name, arguments: argumentsObj })
    if (response.error) throw new Error(response.error.message || `${name} failed`)
    const txt = response.result?.content?.[0]?.text
    return txt ? JSON.parse(txt) : {}
  }

  async listTools() {
    const response = await this.send('tools/list', {})
    if (response.error) throw new Error(response.error.message || 'tools/list failed')
    return response.result?.tools || []
  }

  async stop() {
    if (this.rl) this.rl.close()
    if (this.proc) this.proc.kill('SIGTERM')
  }
}

function ask(rl, text) {
  return new Promise(resolveAnswer => rl.question(text, answer => resolveAnswer(answer.trim())))
}

function splitCommand(line) {
  const tokens = line.trim().split(/\s+/)
  return { command: tokens[0] || '', args: tokens.slice(1) }
}

function collectFindings(...reports) {
  const out = []
  for (const report of reports) {
    if (!report || typeof report !== 'object') continue
    const findings = report.findings
    if (Array.isArray(findings)) {
      for (const item of findings) {
        if (typeof item === 'string' && item.trim()) out.push(item.trim())
      }
    }
  }
  return out
}

async function chooseManuscript(client, cwd) {
  const discovered = await client.callTool('discover_manuscript', { cwd })
  const manuscripts = Array.isArray(discovered.manuscripts) ? discovered.manuscripts : []
  if (manuscripts.length === 0) return null
  return manuscripts[0]?.path || null
}

async function runReviewFlow(client, state, manuscriptPath, mode) {
  const path = resolve(manuscriptPath)
  const isDocx = path.toLowerCase().endsWith('.docx')
  const parseTool = isDocx ? 'parse_docx' : 'parse_pdf'
  const started = new Date().toISOString().replace(/[:.]/g, '-')
  const runDir = join(runRoot, `${started}-${state.activeProfile}-${basename(path).replace(/[^a-zA-Z0-9._-]/g, '_')}`)

  console.log(`• Parsing manuscript with ${parseTool}...`)
  const parsed = await client.callTool(parseTool, { file_path: path })

  console.log('• Mapping sections...')
  const sectionMap = await client.callTool('map_sections', {
    content: parsed.content || '',
    headings: parsed.metadata?.headings || [],
  })

  console.log('• Running analysis passes...')
  const digest = await client.callTool('digest_manuscript', { content: parsed.content || '' })
  const terminology = await client.callTool('analyze_terminology', { content: parsed.content || '' })
  const coherence = await client.callTool('analyze_coherence', { content: parsed.content || '' })
  const methods = await client.callTool('analyze_methods', { content: parsed.content || '' })
  const figuresTables = await client.callTool('analyze_figures_tables', { content: parsed.content || '' })
  const citations = await client.callTool('analyze_citations', { content: parsed.content || '' })
  const format = await client.callTool('analyze_journal_format', { content: parsed.content || '' })
  const lineEdits = await client.callTool('generate_line_edits', { content: parsed.content || '' })

  const findings = collectFindings(terminology, coherence, methods, figuresTables, citations, format)
  console.log('• Arbitrating consolidated review...')
  const arbitration = await client.callTool('arbitrate_review', {
    findings,
    profile: state.activeProfile,
  })

  const inventory = modelInventory()
  const modelTarget = pickModel(state.activeProfile, inventory.models)
  const reviewData = {
    profile: state.activeProfile,
    mode,
    model_target: modelTarget,
    manuscript_path: path,
    comments: findings,
    digest,
    section_map: sectionMap.section_map || {},
    terminology_definition_report: terminology,
    coherence_transition_report: coherence,
    methods_report: methods,
    figure_table_reference_report: figuresTables,
    citation_verification_ledger: citations,
    format_compliance_report: format,
    manuscript_suggested_changes_manifest: lineEdits,
    arbitration,
  }

  mkdirSync(runDir, { recursive: true })
  console.log(`• Rendering artifacts -> ${relative(projectRoot, runDir)}`)
  await client.callTool('render_outputs', { review_data: reviewData, output_dir: runDir })

  console.log('• Validating artifacts...')
  const validation = await client.callTool('validate_outputs', { output_dir: runDir })

  state.lastRunDir = runDir
  saveState(state)

  const quality = findings.length >= 8 ? 'strong' : findings.length >= 4 ? 'moderate' : 'weak'
  console.log(`✓ Review completed. findings=${findings.length}, quality=${quality}, valid=${validation.valid ? 'yes' : 'no'}`)
  console.log(`  Run dir: ${runDir}`)
}

function printHelp() {
  console.log('Commands:')
  console.log('  /wizard                           Guided flow: project -> profile -> review')
  console.log('  /project [index|name]             List or select active project')
  console.log('  /profile [index|name]             List or select profile')
  console.log('  /review [path]                    Run standard review on manuscript')
  console.log('  /deep-run [path]                  Run deep review on manuscript')
  console.log('  /artifacts [run-id-or-path]       Validate and summarize artifacts')
  console.log('  /doctor                           Local backend/models readiness')
  console.log('  /diagnose                         Tool surface + active state')
  console.log('  /replay <run-id-or-path>          Replay run summary')
  console.log('  /diff <run-a> <run-b>             Diff two runs')
  console.log('  /help                             Show this help')
  console.log('  /quit                             Exit')
}

async function main() {
  mkdirSync(runRoot, { recursive: true })
  const state = loadState()
  const client = new BridgeClient(projectRoot)

  console.log('claude-review-v2 interactive shell')
  console.log('OpenClaude-style command loop for manuscript review.')
  console.log(`Active project: ${displayPath(state.activeProjectDir)}`)
  console.log(`Active profile: ${state.activeProfile}`)
  printHelp()
  console.log('')

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true })

  try {
    while (true) {
      const line = await ask(rl, 'claude-review> ')
      if (!line) continue
      const { command, args } = splitCommand(line)

      if (command === '/quit' || command === '/exit') break
      if (command === '/help') {
        printHelp()
        continue
      }

      try {
        if (command === '/project') {
          const projects = listProjectDirs()
          if (projects.length === 0) {
            console.log('No projects found under ./projects; using repo root.')
            state.activeProjectDir = projectRoot
            saveState(state)
            continue
          }
          if (args.length === 0) {
            console.log('Projects:')
            projects.forEach((p, idx) => {
              const marker = resolve(p) === resolve(state.activeProjectDir) ? '*' : ' '
              console.log(` ${marker} ${idx + 1}. ${displayPath(p)}`)
            })
            const summary = await client.callTool('inspect_project', { cwd: state.activeProjectDir })
            console.log(`Active project manuscripts: ${summary.manuscript_count}`)
            continue
          }
          const key = args.join(' ')
          let selected = null
          const idx = Number(key)
          if (Number.isFinite(idx) && idx >= 1 && idx <= projects.length) {
            selected = projects[idx - 1]
          } else {
            selected = projects.find(p => relative(projectRoot, p).includes(key)) || null
          }
          if (!selected) {
            console.log('Project not found.')
            continue
          }
          state.activeProjectDir = selected
          saveState(state)
          const summary = await client.callTool('inspect_project', { cwd: state.activeProjectDir })
          console.log(`Active project set: ${displayPath(selected)} (manuscripts=${summary.manuscript_count})`)
          continue
        }

        if (command === '/profile') {
          if (args.length === 0) {
            console.log('Profiles:')
            profileCatalog.forEach((p, idx) => {
              const marker = p.id === state.activeProfile ? '*' : ' '
              console.log(` ${marker} ${idx + 1}. ${p.id} - ${p.label}`)
            })
            const inv = modelInventory()
            console.log(`Models detected: ${inv.ok ? inv.models.length : 0}`)
            if (inv.ok) {
              console.log(`Gemma4 availability: 26b=${inv.models.includes('gemma4:26b')}, 31b=${inv.models.includes('gemma4:31b')}`)
            }
            continue
          }
          const key = args.join(' ')
          let selected = null
          const idx = Number(key)
          if (Number.isFinite(idx) && idx >= 1 && idx <= profileCatalog.length) {
            selected = profileCatalog[idx - 1].id
          } else {
            selected = profileCatalog.find(p => p.id === key)?.id || null
          }
          if (!selected) {
            console.log('Unknown profile.')
            continue
          }
          state.activeProfile = selected
          saveState(state)
          console.log(`Active profile set: ${selected}`)
          continue
        }

        if (command === '/doctor') {
          const inspect = await client.callTool('inspect_project', { cwd: state.activeProjectDir })
          const inv = modelInventory()
          console.log(`Project: ${displayPath(state.activeProjectDir)}`)
          console.log(`Manuscripts: ${inspect.manuscript_count}`)
          console.log(`Ollama reachable: ${inspect.ollama_running}`)
          console.log(`Local models detected: ${inv.ok ? inv.models.length : 0}`)
          console.log(`Gemma4:26b=${inv.ok && inv.models.includes('gemma4:26b')}, Gemma4:31b=${inv.ok && inv.models.includes('gemma4:31b')}`)
          continue
        }

        if (command === '/diagnose') {
          const tools = await client.listTools()
          console.log(`Tool count: ${tools.length}`)
          console.log(`Active project: ${displayPath(state.activeProjectDir)}`)
          console.log(`Active profile: ${state.activeProfile}`)
          console.log(`Last run: ${state.lastRunDir ? relative(projectRoot, state.lastRunDir) : '(none)'}`)
          continue
        }

        if (command === '/wizard') {
          console.log('Step 1/3: choose project with /project (or press Enter to keep current).')
          const pAns = await ask(rl, 'project> ')
          if (pAns) {
            const fakeLine = `/project ${pAns}`
            const parsed = splitCommand(fakeLine)
            args.splice(0, args.length, ...parsed.args)
            // reuse handler by falling through a local call
            const key = args.join(' ')
            const projects = listProjectDirs()
            let selected = null
            const idx = Number(key)
            if (Number.isFinite(idx) && idx >= 1 && idx <= projects.length) selected = projects[idx - 1]
            if (!selected) selected = projects.find(p => relative(projectRoot, p).includes(key)) || null
            if (selected) {
              state.activeProjectDir = selected
              saveState(state)
              console.log(`Active project set: ${displayPath(selected)}`)
            }
          }

          console.log('Step 2/3: choose profile with /profile (or press Enter to keep current).')
          const profAns = await ask(rl, 'profile> ')
          if (profAns) {
            const key = profAns.trim()
            let selected = null
            const idx = Number(key)
            if (Number.isFinite(idx) && idx >= 1 && idx <= profileCatalog.length) selected = profileCatalog[idx - 1].id
            if (!selected) selected = profileCatalog.find(p => p.id === key)?.id || null
            if (selected) {
              state.activeProfile = selected
              saveState(state)
              console.log(`Active profile set: ${selected}`)
            }
          }

          console.log('Step 3/3: choose manuscript path (or Enter for auto-discover).')
          const fileAns = await ask(rl, 'manuscript> ')
          const chosen = fileAns || await chooseManuscript(client, state.activeProjectDir)
          if (!chosen) {
            console.log('No manuscript found. Add a .pdf or .docx in the active project.')
            continue
          }
          await runReviewFlow(client, state, chosen, 'guided_review')
          continue
        }

        if (command === '/review' || command === '/deep-run') {
          const manuscriptPath = args.length > 0 ? resolve(args.join(' ')) : await chooseManuscript(client, state.activeProjectDir)
          if (!manuscriptPath) {
            console.log('No manuscript detected. Provide a file path: /review path/to/file.pdf')
            continue
          }
          await runReviewFlow(client, state, manuscriptPath, command === '/deep-run' ? 'deep_review' : 'standard_review')
          continue
        }

        if (command === '/artifacts') {
          const runId = args[0] || state.lastRunDir
          if (!runId) {
            console.log('No run selected. Use /review first or /artifacts <run-id-or-path>.')
            continue
          }
          const snapshot = await client.callTool('replay_run', { run_id: runId, cwd: projectRoot })
          const runDir = snapshot.run_dir || runId
          const validation = await client.callTool('validate_outputs', { output_dir: runDir })
          console.log(`Run: ${runDir}`)
          console.log(`Valid: ${validation.valid}`)
          console.log(`Missing artifacts: ${(validation.missing_artifacts || []).length}`)
          continue
        }

        if (command === '/replay') {
          if (args.length === 0) {
            console.log('Usage: /replay <run-id-or-path>')
            continue
          }
          const replay = await client.callTool('replay_run', { run_id: args[0], cwd: projectRoot })
          const summary = replay.run_summary || {}
          console.log(`Run: ${replay.run_dir || args[0]}`)
          console.log(`Profile: ${summary.profile || 'unknown'}`)
          console.log(`Comments: ${(replay.comments || []).length}`)
          continue
        }

        if (command === '/diff') {
          if (args.length < 2) {
            console.log('Usage: /diff <run-a> <run-b>')
            continue
          }
          const diff = await client.callTool('diff_run', { run_id_a: args[0], run_id_b: args[1], cwd: projectRoot })
          console.log(`Δ comments: ${diff.comment_delta}`)
          console.log(`A: ${diff.comment_count_a} comments, B: ${diff.comment_count_b} comments`)
          continue
        }

        console.log('Unknown command. Type /help.')
      } catch (error) {
        console.error(`Command failed: ${error instanceof Error ? error.message : String(error)}`)
      }
    }
  } finally {
    rl.close()
    await client.stop()
    saveState(state)
  }
}

await main()
