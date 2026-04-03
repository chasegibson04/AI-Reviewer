import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { detectManuscripts } from '../../utils/manuscriptDetection.js'
import { getCwd } from '../../utils/cwd.js'
import { lazySchema } from '../../utils/lazySchema.js'

const inputSchema = lazySchema(() => z.strictObject({}))
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() => z.array(z.object({
  path: z.string(),
  type: z.enum(['docx', 'pdf'])
})))
type OutputSchema = ReturnType<typeof outputSchema>

export const DiscoverManuscriptTool = buildTool({
  name: 'discover_manuscript',
  searchHint: 'discover manuscript files in the project',
  async description() {
    return 'Search for manuscript files (.docx, .pdf) in the current directory and projects/ subfolder.'
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  async call(_input, _context) {
    const manuscripts = await detectManuscripts(getCwd())
    return {
      data: manuscripts,
    }
  },
  renderToolUseMessage(_input) {
    return 'Discovering manuscripts...'
  },
  renderToolResultMessage(data) {
    if (data.length === 0) return 'No manuscripts found.'
    return `Found manuscripts:\n${data.map(m => `- ${m.path} (${m.type})`).join('\n')}`
  },
  userFacingName: () => 'DiscoverManuscript',
} satisfies ToolDef<InputSchema, any>)
