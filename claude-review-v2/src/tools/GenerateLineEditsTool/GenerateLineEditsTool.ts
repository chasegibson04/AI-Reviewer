import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const GenerateLineEditsTool = buildTool({
  name: 'generate_line_edits',
  searchHint: 'generate specific line edits',
  async description() {
    return 'Generate specific, grounded line-level edits for improving clarity and flow.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__generate_line_edits')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or generate_line_edits tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Generating line edits...'
  },
  userFacingName: () => 'GenerateLineEdits',
} satisfies ToolDef<InputSchema, any>)
