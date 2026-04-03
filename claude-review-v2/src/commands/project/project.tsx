import type { LocalJSXCommandCall } from '../../types/command.js'
import { getCwd } from '../../utils/cwd.js'
import { detectProjectSnapshots, detectManuscripts } from '../../utils/manuscriptDetection.js'

export const call: LocalJSXCommandCall = async (onDone, context, _args) => {
  const cwd = getCwd()
  const [manuscripts, projects] = await Promise.all([
    detectManuscripts(cwd),
    detectProjectSnapshots(cwd),
  ])
  const bridgeConnected = Object.keys(context.getAppState().mcp.servers).includes(
    'review-bridge',
  )

  const lines: string[] = []
  lines.push('## Project Status')
  lines.push(`- Workspace: \`${cwd}\``)
  lines.push(`- Review bridge: ${bridgeConnected ? 'connected' : 'disconnected'}`)
  lines.push(`- Manuscripts detected: ${manuscripts.length}`)
  lines.push(`- Projects detected: ${projects.length}`)
  if (projects.length > 0) {
    lines.push('')
    lines.push('### Projects')
    for (const project of projects.slice(0, 10)) {
      lines.push(
        `- \`${project.projectId}\` manuscripts=${project.manuscriptCount} runs=${project.artifactCount}`,
      )
    }
  }
  lines.push('')
  lines.push('### Next Actions')
  lines.push('1. Run `/diagnose` to verify local backend and bridge health.')
  lines.push('2. Run `/review` for standard manuscript analysis.')
  lines.push('3. Run `/deep-run` for staged manuscript review execution.')
  lines.push('4. Run `/artifacts` to inspect generated output bundles.')

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
