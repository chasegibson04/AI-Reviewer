import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const AnalyzeCoherenceTool = buildTool({
  name: 'analyze_coherence',
  searchHint: 'analyze logical coherence and flow',
  async description() {
    return 'Analyze logical flow and transitions between sections and paragraphs.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__analyze_coherence')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or analyze_coherence tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Analyzing narrative coherence...'
  },
  userFacingName: () => 'AnalyzeCoherence',
} satisfies ToolDef<InputSchema, any>)
