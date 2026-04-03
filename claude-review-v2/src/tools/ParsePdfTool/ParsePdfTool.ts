import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  file_path: z.string().describe('The path to the .pdf file to parse')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const ParsePdfTool = buildTool({
  name: 'parse_pdf',
  searchHint: 'parse PDF manuscript content',
  async description() {
    return 'Extract text and metadata from a .pdf manuscript file.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__parse_pdf')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or parse_pdf tool missing.")
  },
  renderToolUseMessage(input) {
    return `Parsing PDF: ${input.file_path}...`
  },
  userFacingName: () => 'ParsePdf',
} satisfies ToolDef<InputSchema, any>)
