import type { LocalJSXCommandCall } from '../../types/command.js'
import { getCwd } from '../../utils/cwd.js'
import { detectManuscripts, detectProjectSnapshots, isOllamaRunning } from '../../utils/manuscriptDetection.js'
import {
  DEFAULT_REVIEW_PROFILE,
  fetchOllamaInventory,
  profileAvailabilitySummary,
  resolveProfileModel,
  resolveReviewProfileSelection,
} from '../../utils/model/reviewProfiles.js'
import { getMainLoopModelOverride } from '../../bootstrap/state.js'

export const call: LocalJSXCommandCall = async (onDone, context, _args) => {
  const cwd = getCwd()
  const [ollamaOk, manuscripts, projects, inventory] = await Promise.all([
    isOllamaRunning(),
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
  lines.push('## Diagnose')
  lines.push(`- Ollama backend: ${ollamaOk ? 'running' : 'offline'}`)
  lines.push(`- Ollama inventory: ${profileAvailabilitySummary(inventory)}`)
  lines.push(`- Review bridge server: ${bridgeConnected ? 'connected' : 'disconnected'}`)
  lines.push(`- Manuscripts detected: ${manuscripts.length}`)
  lines.push(`- Projects detected: ${projects.length}`)
  lines.push(`- Selected review profile: \`${selectedProfile}\``)
  lines.push(`- Resolved model target: \`${selectedResolution.resolvedModel}\``)
  lines.push(
    `- Suggested deep reasoning mode: ${
      selectedProfile === 'one_big_model' ||
      selectedProfile === 'full_manuscript_final_pass' ||
      selectedProfile === 'gemma4_26b' ||
      selectedProfile === 'gemma4_31b'
        ? 'gemma_single'
        : 'moe'
    }`,
  )
  lines.push(`- Gemma4 26B detected: ${inventory.hasGemma4_26b ? 'yes' : 'no'}`)
  lines.push(`- Gemma4 31B detected: ${inventory.hasGemma4_31b ? 'yes' : 'no'}`)
  lines.push('')
  lines.push('### Readiness')
  if (ollamaOk && bridgeConnected) {
    lines.push('- System is ready for local-first review workflows.')
  } else {
    lines.push('- System is not fully ready.')
    if (!ollamaOk) {
      lines.push('- Start Ollama (`ollama serve`) and confirm local models are available.')
    }
    if (!bridgeConnected) {
      lines.push(
        '- Ensure `review-bridge` MCP server is configured and Python dependencies are installed.',
      )
    }
  }
  if (
    (selectedProfile === 'one_big_model' ||
      selectedProfile === 'full_manuscript_final_pass') &&
    !inventory.hasGemma4_26b &&
    !inventory.hasGemma4_31b
  ) {
    lines.push(
      '- Big-model profile is selected, but Gemma 4 was not detected. Fallback model will be used.',
    )
  }

  if (
    bridgeConnected &&
    (selectedResolution.resolvedModel.startsWith('gemma4:') ||
      selectedProfile === 'one_big_model' ||
      selectedProfile === 'full_manuscript_final_pass' ||
      selectedProfile === 'gemma4_26b' ||
      selectedProfile === 'gemma4_31b')
  ) {
    const probeTool = context
      .getAppState()
      .mcpTools.find(tool => tool.name === 'mcp__review_bridge__diagnose_model')
    if (probeTool) {
      try {
        const probe = await probeTool.call({ model: selectedResolution.resolvedModel }, context) as {
          usable?: boolean
          short_prompt?: { status?: string }
          medium_prompt?: { status?: string }
          json_prompt?: { status?: string }
          ingest_prompt?: { status?: string }
          citation_prompt?: { status?: string }
          long_review_prompt?: { status?: string }
        }
        lines.push(
          `- Gemma probe (${selectedResolution.resolvedModel}): usable=${
            probe.usable ? 'yes' : 'no'
          }, short=${probe.short_prompt?.status ?? 'unknown'}, medium=${
            probe.medium_prompt?.status ?? 'unknown'
          }, json=${probe.json_prompt?.status ?? 'unknown'}, ingest=${
            probe.ingest_prompt?.status ?? 'unknown'
          }, citation=${probe.citation_prompt?.status ?? 'unknown'}, long=${
            probe.long_review_prompt?.status ?? 'unknown'
          }`,
        )
      } catch {
        lines.push('- Gemma probe: unavailable (diagnostic tool call failed).')
      }
    }
  }

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
