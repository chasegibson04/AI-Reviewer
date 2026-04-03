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
    return [
      {
        type: 'text',
        text: `Replay a prior manuscript review run.
- Call replay_run with run_id="${args}".
- Summarize run_summary, section_map coverage, comment counts, and suggested changes.
- If replay fails, explain exactly what run identifiers/paths are valid.
- Do not fabricate artifacts.`,
      },
    ]
  },
}

export default replay
