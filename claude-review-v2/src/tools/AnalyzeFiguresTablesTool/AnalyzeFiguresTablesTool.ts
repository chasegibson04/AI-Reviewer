import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const AnalyzeFiguresTablesTool = buildTool({
  name: 'analyze_figures_tables',
  searchHint: 'analyze figures and tables',
  async description() {
    return 'Analyze clarity and correctness of data presentation in figures and tables.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__analyze_figures_tables')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or analyze_figures_tables tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Analyzing figures and tables...'
  },
  userFacingName: () => 'AnalyzeFiguresTables',
} satisfies ToolDef<InputSchema, any>)
