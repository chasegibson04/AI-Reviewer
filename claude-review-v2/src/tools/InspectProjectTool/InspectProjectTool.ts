import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { getCwd } from '../../utils/cwd.js'
import { getEnvironmentSummary } from '../../utils/manuscriptDetection.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({}))
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() => z.string())
type OutputSchema = ReturnType<typeof outputSchema>

export const InspectProjectTool = buildTool({
  name: 'inspect_project',
  searchHint: 'inspect current project for manuscripts and backend status',
  async description() {
    return 'Inspect the current directory for manuscripts (.docx, .pdf) and check if the local Ollama backend is running.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  async call(_input, context) {
    const { mcpTools } = context.getAppState()
    const bridgeTool = mcpTools.find(t => t.name === 'mcp__review_bridge__inspect_project')
    if (bridgeTool) return await bridgeTool.call({ cwd: getCwd() }, context)

    const summary = await getEnvironmentSummary(getCwd())
    return {
      data: summary,
    }
  },
  renderToolUseMessage(_input) {
    return 'Inspecting project...'
  },
  renderToolResultMessage(data) {
    return data
  },
  userFacingName: () => 'InspectProject',
} satisfies ToolDef<InputSchema, string>)
