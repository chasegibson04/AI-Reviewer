import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  findings: z.array(z.string()).describe('List of review findings to arbitrate'),
  profile: z.string().optional().describe('The review profile to use for arbitration')
}))
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() => z.object({
  summary: z.string(),
  recommendation: z.enum(['minor_revision', 'major_revision', 'reject']),
  score: z.number().optional(),
  profile: z.string().optional(),
}))
type OutputSchema = ReturnType<typeof outputSchema>

export const ArbitrateReviewTool = buildTool({
  name: 'arbitrate_review',
  searchHint: 'arbitrate multiple review findings',
  async description() {
    return 'Synthesize multiple review findings into a coherent final review report with a formal recommendation.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__arbitrate_review')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or arbitrate_review tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Arbitrating review findings...'
  },
  renderToolResultMessage(data) {
    return `Arbitration complete. Recommendation: ${data.recommendation}`
  },
  userFacingName: () => 'ArbitrateReview',
} satisfies ToolDef<InputSchema, any>)
