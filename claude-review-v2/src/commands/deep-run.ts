import type { ContentBlockParam } from '@anthropic-ai/sdk/resources/messages.js'
import type { Command } from '../commands.js'

const deepReview: Command = {
  type: 'prompt',
  name: 'deep-run',
  description: 'Trigger a staged deep review (local MOE routing)',
  progressMessage: 'performing staged deep review',
  contentLength: 0,
  source: 'builtin',
  async getPromptForCommand(args): Promise<ContentBlockParam[]> {
    return [
      {
        type: 'text',
        text: `Run a full staged manuscript review.

Required flow:
1. Call inspect_project.
2. Resolve manuscript path: use provided args or call discover_manuscript.
3. Parse manuscript (parse_docx or parse_pdf).
4. Call map_sections and digest_manuscript.
5. Run analysis tools: analyze_methods, analyze_coherence, analyze_terminology, analyze_figures_tables, analyze_citations, analyze_journal_format.
6. Call generate_line_edits.
7. Call arbitrate_review on synthesized findings.
8. Build review_data and call render_outputs to write artifacts.
9. Call validate_outputs and report pass/fail with explicit missing/invalid artifacts.

Rules:
- Use local-first behavior and avoid remote network calls.
- Never operate on blocked projects containing pampa or horseshoe.
- Keep all outputs inside the current workspace.

Args: ${args}`,
      },
    ]
  },
}

export default deepReview
