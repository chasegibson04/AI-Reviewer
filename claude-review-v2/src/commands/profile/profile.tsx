import type { LocalJSXCommandCall } from '../../types/command.js'
import {
  getMainLoopModel,
} from '../../utils/model/model.js'
import { getMainLoopModelOverride, setMainLoopModelOverride } from '../../bootstrap/state.js'
import {
  DEFAULT_REVIEW_PROFILE,
  fetchOllamaInventory,
  getReviewProfileOptions,
  profileAvailabilitySummary,
  resolveProfileModel,
  resolveReviewProfileSelection,
} from '../../utils/model/reviewProfiles.js'

export const call: LocalJSXCommandCall = async (onDone, _context, args) => {
  const trimmed = args.trim()
  const inventory = await fetchOllamaInventory()
  const options = getReviewProfileOptions()

  if (trimmed.length > 0) {
    if (trimmed === 'reset' || trimmed === 'clear') {
      setMainLoopModelOverride(undefined)
      onDone(
        `Profile override cleared. Default review profile is \`${DEFAULT_REVIEW_PROFILE}\`.`,
        { display: 'system' },
      )
      return null
    }

    const selected = resolveReviewProfileSelection(trimmed)
    if (!selected) {
      onDone(
        `Unknown profile selection \`${trimmed}\`. Run \`/profile\` to view numbered options.`,
        { display: 'system' },
      )
      return null
    }

    const resolution = resolveProfileModel(selected, inventory)
    setMainLoopModelOverride(selected)

    const lines: string[] = []
    lines.push(`Profile override set to \`${selected}\`.`)
    lines.push(`- Mode: ${resolution.mode}`)
    lines.push(`- Resolved model target: \`${resolution.resolvedModel}\``)
    lines.push(`- Fallback used: ${resolution.fallbackUsed ? 'yes' : 'no'}`)
    for (const note of resolution.notes) {
      lines.push(`- Note: ${note}`)
    }
    onDone(lines.join('\n'), { display: 'system' })
    return null
  }

  const override = getMainLoopModelOverride()
  const current = getMainLoopModel()
  const activeSelection =
    typeof override === 'string'
      ? resolveReviewProfileSelection(override) ?? DEFAULT_REVIEW_PROFILE
      : DEFAULT_REVIEW_PROFILE

  const lines: string[] = []
  lines.push('## Review Profile Selection')
  lines.push(`- Current runtime model: \`${current}\``)
  lines.push(`- Active override: ${override ? `\`${String(override)}\`` : 'none'}`)
  lines.push(`- Effective review profile default: \`${activeSelection}\``)
  lines.push(`- Inventory: ${profileAvailabilitySummary(inventory)}`)
  lines.push('')
  lines.push('Selectable run styles:')
  for (const [index, option] of options.entries()) {
    const resolution = resolveProfileModel(option.alias, inventory)
    const activeMarker = option.alias === activeSelection ? ' (active)' : ''
    lines.push(
      `${index + 1}. \`${option.alias}\`${activeMarker} - ${option.label}: ${option.description}`,
    )
    lines.push(
      `   target=\`${resolution.resolvedModel}\`, fallback=${resolution.fallbackUsed ? 'yes' : 'no'}`,
    )
  }
  lines.push('')
  lines.push('Usage examples:')
  lines.push('- `/profile 3` (select by number)')
  lines.push('- `/profile moe`')
  lines.push('- `/profile big`')
  lines.push('- `/profile full_manuscript_final_pass`')
  lines.push('- `/profile reset`')
  lines.push('')
  lines.push(
    'Big-model mode guidance: use `one_big_model` or `full_manuscript_final_pass`; Gemma 4 is preferred when detected.',
  )

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
