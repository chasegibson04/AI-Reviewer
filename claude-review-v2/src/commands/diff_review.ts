import type { ContentBlockParam } from '@anthropic-ai/sdk/resources/messages.js'
import type { Command } from '../commands.js'

const diffReview: Command = {
  type: 'prompt',
  name: 'diff',
  description: 'Compare findings between two review runs',
  progressMessage: 'comparing review runs',
  contentLength: 0,
  source: 'builtin',
  async getPromptForCommand(args): Promise<ContentBlockParam[]> {
    return [
      {
        type: 'text',
        text: `Compare two manuscript review runs.
- Parse args into run_id_a and run_id_b.
- Call diff_run once with both IDs.
- Report changes in comments, sections, and any risk deltas.
- If IDs are invalid, return exact failure details and recovery steps.

Args: ${args}`,
      },
    ]
  },
}

export default diffReview
