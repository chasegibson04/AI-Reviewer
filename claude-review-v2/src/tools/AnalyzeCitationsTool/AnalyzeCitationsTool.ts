import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const AnalyzeCitationsTool = buildTool({
  name: 'analyze_citations',
  searchHint: 'analyze citations and references',
  async description() {
    return 'Verify citation accuracy, relevance, and formatting.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__analyze_citations')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or analyze_citations tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Verifying citations and references...'
  },
  userFacingName: () => 'AnalyzeCitations',
} satisfies ToolDef<InputSchema, any>)
