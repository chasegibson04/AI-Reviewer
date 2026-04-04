import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  file_path: z.string().describe('The path to the .docx file to parse')
}))
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() => z.object({
  content: z.string(),
  metadata: z.record(z.any())
}))
type OutputSchema = ReturnType<typeof outputSchema>

export const ParseDocxTool = buildTool({
  name: 'parse_docx',
  searchHint: 'parse DOCX manuscript content',
  async description() {
    return 'Extract text and metadata from a .docx manuscript file.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const parseDocxTool = mcpTools.find(t => t.name === 'mcp__review_bridge__parse_docx')
    if (parseDocxTool) return await parseDocxTool.call({ file_path: input.file_path }, context)
    throw new Error("review-bridge MCP server not found or parse_docx tool missing.")
  },
  renderToolUseMessage(input) {
    return `Parsing DOCX: ${input.file_path}...`
  },
  renderToolResultMessage(data) {
    return `Parsed DOCX successfully (${data.content.length} characters).`
  },
  userFacingName: () => 'ParseDocx',
} satisfies ToolDef<InputSchema, any>)
