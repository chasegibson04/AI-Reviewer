import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  run_id: z.string().describe('ID of the run to replay')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const ReplayRunTool = buildTool({
  name: 'replay_run',
  searchHint: 'replay previous review run',
  async description() {
    return 'Replay a previous review run from its local artifacts.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__replay_run')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or replay_run tool missing.")
  },
  renderToolUseMessage(input) {
    return `Replaying run: ${input.run_id}...`
  },
  userFacingName: () => 'ReplayRun',
} satisfies ToolDef<InputSchema, any>)
