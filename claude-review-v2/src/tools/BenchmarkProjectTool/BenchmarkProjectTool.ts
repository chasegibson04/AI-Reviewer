import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({
  project_id: z.string().describe('ID of the project to benchmark')
}))
type InputSchema = ReturnType<typeof inputSchema>

export const BenchmarkProjectTool = buildTool({
  name: 'benchmark_project',
  searchHint: 'benchmark project capabilities',
  async description() {
    return 'Benchmark the project capabilities against reference manuscripts and known standards.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): any {
    return z.any()
  },
  async call(input, context) {
    const { mcpTools } = context.getAppState()
    const tool = mcpTools.find(t => t.name === 'mcp__review_bridge__benchmark_project')
    if (tool) return await tool.call(input, context)
    throw new Error("review-bridge MCP server not found or benchmark_project tool missing.")
  },
  renderToolUseMessage(input) {
    return `Benchmarking project: ${input.project_id}...`
  },
  userFacingName: () => 'BenchmarkProject',
} satisfies ToolDef<InputSchema, any>)
