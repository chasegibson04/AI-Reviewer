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
    return [{
      type: 'text',
      text: `Compare two review runs. Args: ${args}. Use the diff_run tool to identify changes and discrepancies between the findings.`
    }]
  },
}

export default diffReview
