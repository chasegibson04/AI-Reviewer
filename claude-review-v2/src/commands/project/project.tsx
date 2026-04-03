import type { LocalJSXCommandCall } from '../../types/command.js'
import { getCwd } from '../../utils/cwd.js'
import { detectProjectSnapshots, detectManuscripts } from '../../utils/manuscriptDetection.js'
import {
  DEFAULT_REVIEW_PROFILE,
  fetchOllamaInventory,
  resolveProfileModel,
  resolveReviewProfileSelection,
} from '../../utils/model/reviewProfiles.js'
import { getMainLoopModelOverride } from '../../bootstrap/state.js'

export const call: LocalJSXCommandCall = async (onDone, context, _args) => {
  const cwd = getCwd()
  const [manuscripts, projects, inventory] = await Promise.all([
    detectManuscripts(cwd),
    detectProjectSnapshots(cwd),
    fetchOllamaInventory(),
  ])
  const bridgeConnected = Object.keys(context.getAppState().mcp.servers).includes(
    'review-bridge',
  )
  const override = getMainLoopModelOverride()
  const selectedProfile =
    typeof override === 'string'
      ? resolveReviewProfileSelection(override) ?? DEFAULT_REVIEW_PROFILE
      : DEFAULT_REVIEW_PROFILE
  const selectedResolution = resolveProfileModel(selectedProfile, inventory)

  const lines: string[] = []
  lines.push('## Project Status')
  lines.push(`- Workspace: \`${cwd}\``)
  lines.push(`- Review bridge: ${bridgeConnected ? 'connected' : 'disconnected'}`)
  lines.push(`- Manuscripts detected: ${manuscripts.length}`)
  lines.push(`- Projects detected: ${projects.length}`)
  lines.push(`- Active review profile: \`${selectedProfile}\``)
  lines.push(`- Active mode: ${selectedResolution.mode}`)
  lines.push(`- Active model target: \`${selectedResolution.resolvedModel}\``)
  lines.push(`- Gemma4 26B available: ${inventory.hasGemma4_26b ? 'yes' : 'no'}`)
  lines.push(`- Gemma4 31B available: ${inventory.hasGemma4_31b ? 'yes' : 'no'}`)
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
  lines.push('2. Run `/profile` and choose MOE vs big-model style.')
  lines.push('3. Run `/review` for standard manuscript analysis.')
  lines.push('4. Run `/deep-run` for staged manuscript review execution.')
  lines.push('5. Run `/artifacts` to inspect generated output bundles.')

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
