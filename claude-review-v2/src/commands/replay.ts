import type { ContentBlockParam } from '@anthropic-ai/sdk/resources/messages.js'
import type { Command } from '../commands.js'

const replay: Command = {
  type: 'prompt',
  name: 'replay',
  description: 'Replay a previous review from local artifacts',
  progressMessage: 'replaying review',
  contentLength: 0,
  source: 'builtin',
  async getPromptForCommand(args): Promise<ContentBlockParam[]> {
    return [{
      type: 'text',
      text: `Replay the review run with ID: ${args}. Use the replay_run tool to load artifacts and present the findings.`
    }]
  },
}

export default replay
