import type { LocalJSXCommandCall } from '../../types/command.js'
import {
  getMainLoopModel,
  parseUserSpecifiedModel,
} from '../../utils/model/model.js'
import { getMainLoopModelOverride, setMainLoopModelOverride } from '../../bootstrap/state.js'

const SUPPORTED_PROFILES = [
  'quick_local',
  'balanced_local',
  'deep_local',
  'local_moe',
  'one_big_model',
  'full_manuscript_final_pass',
  'offline_strict',
  'llama_cpp_standard',
  'llama_cpp_turboquant',
  'gemma4_26b',
  'gemma4_31b',
] as const

export const call: LocalJSXCommandCall = async (onDone, _context, args) => {
  const trimmed = args.trim()

  if (trimmed.length > 0) {
    try {
      const resolved = parseUserSpecifiedModel(trimmed)
      setMainLoopModelOverride(trimmed)
      onDone(
        `Profile override set to \`${trimmed}\` (resolved model: \`${resolved}\`).`,
        { display: 'system' },
      )
      return null
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      onDone(`Failed to set profile: ${msg}`, { display: 'system' })
      return null
    }
  }

  const override = getMainLoopModelOverride()
  const current = getMainLoopModel()

  const lines: string[] = []
  lines.push('## Profile')
  lines.push(`- Current runtime model: \`${current}\``)
  lines.push(`- Active override: ${override ? `\`${String(override)}\`` : 'none'}`)
  lines.push('')
  lines.push('Supported profile aliases:')
  for (const profile of SUPPORTED_PROFILES) {
    lines.push(`- \`${profile}\``)
  }
  lines.push('')
  lines.push('Usage:')
  lines.push('- `/profile balanced_local`')
  lines.push('- `/profile deep_local`')
  lines.push('- `/profile local_moe`')

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
