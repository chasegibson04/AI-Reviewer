import type { ContentBlockParam } from '@anthropic-ai/sdk/resources/messages.js'
import type { Command } from '../commands.js'
import { getMainLoopModelOverride } from '../bootstrap/state.js'
import { fetchOllamaInventory, resolveProfileModel } from '../utils/model/reviewProfiles.js'
import { parseReviewRunParameters } from './review/runParameters.js'

const MANUSCRIPT_REVIEW_PROMPT = (
  args: string,
  selectedProfile: string,
  resolvedModel: string,
  mode: string,
  notes: string[],
  reasoningMode: 'moe' | 'gemma_single',
  reasoningModeExplicit: boolean,
) => `
      You are an expert manuscript reviewer and scientific editor. Your goal is to provide a comprehensive, high-quality review of a scientific manuscript.

      Active run profile: ${selectedProfile}
      Active run mode: ${mode}
      Deep reasoning mode requested: ${reasoningMode}
      Deep reasoning mode explicit: ${reasoningModeExplicit ? 'yes' : 'no'}
      Primary model target: ${resolvedModel}
      Profile notes: ${notes.join(' | ') || 'none'}

      Follow these steps to conduct the review:

      1. **Discover Manuscripts**: If no file path is provided in the args, use \`discover_manuscript\` to find available manuscript files.
      2. **Inspect Environment**: Use \`inspect_project\` to ensure the environment is ready and relevant tools are available.
      3. **Parse & Map**: Use \`parse_docx\` or \`parse_pdf\` on the selected manuscript, followed by \`map_sections\` to understand the document structure.
      4. **In-Depth Analysis**: Prefer \`generate_deep_review\` for staged model-backed synthesis, and fall back to specialized analysis tools as needed:
         - \`analyze_methods\` for methodological skepticism and rigor.
         - \`analyze_coherence\` for logical flow and transitions.
         - \`analyze_terminology\` for consistent and precise language.
         - \`analyze_figures_tables\` for clarity and correctness of data presentation.
         - \`analyze_citations\` for citation marker coverage.
         - Ensure line-by-line citation verification and support-paper ingest outputs are preserved from \`generate_deep_review\`.
      5. **Arbitration**: Use \`arbitrate_review\` to synthesize findings into a coherent set of recommendations.
      6. **Output Generation**: Use \`render_outputs\` to generate final artifacts and \`validate_outputs\` to ensure correctness.
      7. **Honest Reporting**: If a tool fails or returns missing data, state that explicitly and do not claim completion.

      Focus on:
      - Scientific rigor and methodological soundness.
      - Clarity and coherence of the narrative.
      - Adherence to academic standards and journal formatting.
      - Actionable feedback for the authors.
      - Local-first execution (avoid remote network usage unless explicitly requested).
      - Never operate on blocked project IDs containing PAMPA/pampa or horseshoe.
      - Reflect the chosen profile in routing_trace and run_summary outputs.
      - Include reasoning_mode_requested and reasoning_mode_effective in run_summary.
      - Preserve machine-readable support ingest and citation verification manifests while keeping visible comments concise.

      Args (e.g., file path): ${args}
    `

const review: Command = {
  type: 'prompt',
  name: 'review',
  description: 'Review a scientific manuscript',
  progressMessage: 'reviewing manuscript',
  contentLength: 0,
  source: 'builtin',
  async getPromptForCommand(args): Promise<ContentBlockParam[]> {
    const override = getMainLoopModelOverride()
    const params = parseReviewRunParameters(args, typeof override === 'string' ? override : undefined)
    const inventory = await fetchOllamaInventory()
    const resolution = resolveProfileModel(params.profile, inventory)
    return [
      {
        type: 'text',
        text: MANUSCRIPT_REVIEW_PROMPT(
          params.manuscriptHint || args,
          params.profile,
          resolution.resolvedModel,
          resolution.mode,
          resolution.notes,
          params.reasoningMode,
          params.reasoningModeExplicit,
        ),
      },
    ]
  },
}

export default review
