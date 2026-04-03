import type { LocalJSXCommandCall } from '../../types/command.js'
import { getCwd } from '../../utils/cwd.js'
import { detectManuscripts, detectProjectSnapshots } from '../../utils/manuscriptDetection.js'
import {
  DEFAULT_REVIEW_PROFILE,
  fetchOllamaInventory,
  profileAvailabilitySummary,
  resolveProfileModel,
  resolveReviewProfileSelection,
} from '../../utils/model/reviewProfiles.js'
import { getMainLoopModel, getUserSpecifiedModelSetting } from '../../utils/model/model.js'
import { getMainLoopModelOverride } from '../../bootstrap/state.js'

export const call: LocalJSXCommandCall = async (onDone, context, _args) => {
  const cwd = getCwd()
  const [inventory, manuscripts, projects] = await Promise.all([
    fetchOllamaInventory(),
    detectManuscripts(cwd),
    detectProjectSnapshots(cwd),
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
  lines.push('## Doctor (Manuscript Review)')
  lines.push(`- Workspace: \`${cwd}\``)
  lines.push(`- Bridge server: ${bridgeConnected ? 'connected' : 'disconnected'}`)
  lines.push(`- Ollama status: ${inventory.reachable ? 'reachable' : 'unreachable'}`)
  lines.push(`- Ollama inventory: ${profileAvailabilitySummary(inventory)}`)
  lines.push(`- Current runtime model: \`${getMainLoopModel()}\``)
  lines.push(`- User-specified model setting: \`${String(getUserSpecifiedModelSetting() ?? 'none')}\``)
  lines.push(`- Review profile: \`${selectedProfile}\``)
  lines.push(`- Review mode: ${selectedResolution.mode}`)
  lines.push(`- Resolved model target: \`${selectedResolution.resolvedModel}\``)
  lines.push(`- Manuscripts detected: ${manuscripts.length}`)
  lines.push(`- Projects detected: ${projects.length}`)
  lines.push('')
  lines.push('### Checks')
  lines.push(`- Local backend check: ${inventory.reachable ? 'pass' : 'fail'}`)
  lines.push(`- Bridge connectivity check: ${bridgeConnected ? 'pass' : 'fail'}`)
  lines.push(`- Gemma4 26B availability: ${inventory.hasGemma4_26b ? 'pass' : 'not found'}`)
  lines.push(`- Gemma4 31B availability: ${inventory.hasGemma4_31b ? 'pass' : 'not found'}`)

  if (
    (selectedProfile === 'one_big_model' ||
      selectedProfile === 'full_manuscript_final_pass') &&
    !inventory.hasGemma4_26b &&
    !inventory.hasGemma4_31b
  ) {
    lines.push(
      '- Big-model profile selected without Gemma 4 detected; fallback model path will be used.',
    )
  }

  lines.push('')
  lines.push('### Suggested actions')
  lines.push('1. Run `/profile` to choose balanced/deep/MOE/big-model run style.')
  lines.push('2. Run `/review <file>` for focused review or `/deep-run <file>` for staged deep review.')
  lines.push('3. Run `/artifacts` after a run to inspect output bundles and validation reports.')

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
