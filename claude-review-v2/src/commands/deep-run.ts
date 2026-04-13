import type { ContentBlockParam } from '@anthropic-ai/sdk/resources/messages.js'
import type { Command } from '../commands.js'
import { getMainLoopModelOverride } from '../bootstrap/state.js'
import { fetchOllamaInventory, resolveProfileModel } from '../utils/model/reviewProfiles.js'
import { parseReviewRunParameters } from './review/runParameters.js'

const deepReview: Command = {
  type: 'prompt',
  name: 'deep-run',
  description: 'Trigger a staged deep review (MOE or single-model Gemma 4)',
  progressMessage: 'performing staged deep review',
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
        text: `Run a full staged manuscript review.

Active run profile: ${params.profile}
Active run mode: ${resolution.mode}
Requested deep reasoning mode: ${params.reasoningMode}
Reasoning mode selected explicitly: ${params.reasoningModeExplicit ? 'yes' : 'no'}
Primary model target: ${resolution.resolvedModel}
Profile notes: ${resolution.notes.join(' | ') || 'none'}

Required flow:
1. Call inspect_project.
2. Resolve manuscript path: use provided args or call discover_manuscript.
3. Parse manuscript (parse_docx or parse_pdf).
4. Call map_sections and digest_manuscript.
5. If mode is single-model Gemma, call diagnose_model for the candidate Gemma model before deep generation.
6. Call generate_deep_review with content + profile + reasoning_mode + model_target + section_map + manuscript_path.
7. Ensure support-paper ingest is executed and cached for available citation/source files.
8. Ensure line-by-line citation verification is executed against the reference section, with abstract-only fallback clearly labeled when used.
9. Call arbitrate_review on synthesized findings from generate_deep_review.
10. Build review_data and call render_outputs to write artifacts.
11. Call validate_outputs and report pass/fail with explicit missing/invalid artifacts.

Rules:
- If deep reasoning mode was not selected explicitly, ask the user to choose one before execution:
  - MOE (multi-model specialists)
  - Single-model Gemma 4
- Use local-first behavior and avoid remote network calls.
- Never operate on blocked projects containing pampa or horseshoe.
- Keep all outputs inside the current workspace.
- Include selected profile and model target in routing_trace and run_summary fields.
- Include reasoning_mode_requested and reasoning_mode_effective in run_summary.
- Include support_ingest_report, support_usage_ledger, assertion_ledger, claim_verification_summary, and citation_verification_ledger in review_data.

Args: ${params.manuscriptHint || args}`,
      },
    ]
  },
}

export default deepReview
