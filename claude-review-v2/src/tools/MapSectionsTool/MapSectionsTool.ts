import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  content: z.string().describe('Manuscript text content'),
  headings: z.array(z.string()).optional().describe('Detected headings')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const MapSectionsTool = buildTool({
  name: 'map_sections',
  searchHint: 'map manuscript section structure',
  async description() {
    return 'Map the document structure and identify key scientific sections (Abstract, Methods, etc.).'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__map_sections')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or map_sections tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Mapping manuscript sections...'
  },
  userFacingName: () => 'MapSections',
} satisfies ToolDef<InputSchema, any>)
