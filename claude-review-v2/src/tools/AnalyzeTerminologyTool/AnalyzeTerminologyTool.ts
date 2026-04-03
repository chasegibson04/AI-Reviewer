import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const AnalyzeTerminologyTool = buildTool({
  name: 'analyze_terminology',
  searchHint: 'analyze scientific terminology',
  async description() {
    return 'Analyze consistency and precision of scientific terminology throughout the manuscript.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__analyze_terminology')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or analyze_terminology tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Analyzing terminology consistency...'
  },
  userFacingName: () => 'AnalyzeTerminology',
} satisfies ToolDef<InputSchema, any>)
