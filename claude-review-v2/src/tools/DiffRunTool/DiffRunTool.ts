import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  run_id_a: z.string().describe('First run ID'),
  run_id_b: z.string().describe('Second run ID')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const DiffRunTool = buildTool({
  name: 'diff_run',
  searchHint: 'diff two review runs',
  async description() {
    return 'Compare and diff two different review runs to identify changes in findings.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__diff_run')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or diff_run tool missing.")
  },
  renderToolUseMessage(input) {
    return `Diffing runs: ${input.run_id_a} vs ${input.run_id_b}...`
  },
  userFacingName: () => 'DiffRun',
} satisfies ToolDef<InputSchema, any>)
