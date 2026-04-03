import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  output_dir: z.string().describe('Directory containing artifacts')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const ValidateOutputsTool = buildTool({
  name: 'validate_outputs',
  searchHint: 'validate generated artifacts',
  async description() {
    return 'Verify artifact presence and schema validity for generated review reports.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__validate_outputs')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or validate_outputs tool missing.")
  },
  renderToolUseMessage(_input) {
    return 'Validating review artifacts...'
  },
  userFacingName: () => 'ValidateOutputs',
} satisfies ToolDef<InputSchema, any>)
