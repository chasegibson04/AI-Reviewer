import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const AnalyzeJournalFormatTool = buildTool({
  name: 'analyze_journal_format',
  searchHint: 'check journal formatting compliance',
  async description() {
    return 'Check adherence to specific journal formatting and academic standards.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__analyze_journal_format')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or analyze_journal_format tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Checking formatting compliance...'
  },
  userFacingName: () => 'AnalyzeJournalFormat',
} satisfies ToolDef<InputSchema, any>)
