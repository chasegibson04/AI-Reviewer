import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('The manuscript content to analyze'),
  focus: z.string().optional().describe('Specific focus area for methods analysis')
}))
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() => z.object({
  findings: z.array(z.string()),
  signal_checks: z.record(z.boolean()),
  skepticism_score: z.number(),
}))
type OutputSchema = ReturnType<typeof outputSchema>

export const AnalyzeMethodsTool = buildTool({
  name: 'analyze_methods',
  searchHint: 'analyze research methods in the manuscript',
  async description() {
    return 'Perform a deep analysis of the research methods described in the manuscript, applying scientific skepticism.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const analyzeMethodsTool = mcpTools.find(t => t.name === 'mcp__review_bridge__analyze_methods')
    if (analyzeMethodsTool) return await analyzeMethodsTool.call({ content: input.content, focus: input.focus }, context)
    throw new Error("review-bridge MCP server not found or analyze_methods tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Analyzing research methods...'
  },
  renderToolResultMessage(data) {
    return `Methods analysis complete. Skepticism score: ${data.skepticism_score}`
  },
  userFacingName: () => 'AnalyzeMethods',
} satisfies ToolDef<InputSchema, any>)
