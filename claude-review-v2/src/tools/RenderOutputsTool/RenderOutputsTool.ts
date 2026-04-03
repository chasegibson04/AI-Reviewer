import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  review_data: z.any().describe('The accumulated review findings'),
  output_dir: z.string().describe('Directory to save artifacts')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const RenderOutputsTool = buildTool({
  name: 'render_outputs',
  searchHint: 'render final review artifacts',
  async description() {
    return 'Generate the final review artifacts (JSON and Markdown reports).'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__render_outputs')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or render_outputs tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Rendering review artifacts...'
  },
  userFacingName: () => 'RenderOutputs',
} satisfies ToolDef<InputSchema, any>)
