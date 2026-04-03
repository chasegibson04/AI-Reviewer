import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const DigestManuscriptTool = buildTool({
  name: 'digest_manuscript',
  searchHint: 'create technical digest of manuscript',
  async description() {
    return "Create a high-level technical digest of the manuscript's core claims and findings."
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__digest_manuscript')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or digest_manuscript tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Digesting manuscript content...'
  },
  userFacingName: () => 'DigestManuscript',
} satisfies ToolDef<InputSchema, any>)
