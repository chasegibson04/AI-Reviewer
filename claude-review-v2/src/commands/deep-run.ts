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
    return [{
      type: 'text',
      text: `Perform a staged deep review using the local_moe profile. Follow the full scientific analysis pipeline (methods, coherence, terminology, figures, citations) and arbitrate the results. Args: ${args}`
    }]
  },
}

export default deepReview
