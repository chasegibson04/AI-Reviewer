import type { Dirent } from 'node:fs'
import { readdir } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import type { LocalJSXCommandCall } from '../../types/command.js'
import { getCwd } from '../../utils/cwd.js'

async function getRunDirectories(root: string): Promise<string[]> {
  try {
    const entries: Dirent[] = await readdir(root, { withFileTypes: true })
    return entries.filter(entry => entry.isDirectory()).map(entry => join(root, entry.name))
  } catch {
    return []
  }
}

export const call: LocalJSXCommandCall = async (onDone, _context, _args) => {
  const cwd = getCwd()
  const roots = [
    join(cwd, 'test_outputs'),
    join(cwd, 'outputs'),
    join(cwd, 'projects'),
  ]

  const discovered: string[] = []
  for (const root of roots) {
    const dirs = await getRunDirectories(root)
    discovered.push(...dirs)
  }

  const lines: string[] = []
  lines.push('## Artifacts')
  lines.push(`- Workspace: \`${cwd}\``)
  if (discovered.length === 0) {
    lines.push('- No artifact directories found under `test_outputs/`, `outputs/`, or `projects/`.')
  } else {
    lines.push(`- Found ${discovered.length} artifact directories (showing up to 20):`)
    for (const dir of discovered.slice(0, 20)) {
      lines.push(`- \`${resolve(dir)}\``)
    }
  }
  lines.push('')
  lines.push('Expected core files per run:')
  lines.push('- `run_summary.json`')
  lines.push('- `manuscript_comment_manifest.json`')
  lines.push('- `manuscript_suggested_changes_manifest.json`')
  lines.push('- `tool_event_log.jsonl`')
  lines.push('- `network_event_log.jsonl`')
  lines.push('- `session_transcript.md`')

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
