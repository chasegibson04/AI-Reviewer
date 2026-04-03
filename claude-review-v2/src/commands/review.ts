import type { ContentBlockParam } from '@anthropic-ai/sdk/resources/messages.js'
import type { Command } from '../commands.js'
import { isUltrareviewEnabled } from './review/ultrareviewEnabled.js'

// Legal wants the explicit surface name plus a docs link visible before the
// user triggers, so the description carries "Claude Code on the web" + URL.
const CCR_TERMS_URL = 'https://code.claude.com/docs/en/claude-code-on-the-web'

const MANUSCRIPT_REVIEW_PROMPT = (args: string) => `
      You are an expert manuscript reviewer and scientific editor. Your goal is to provide a comprehensive, high-quality review of a scientific manuscript.

      Follow these steps to conduct the review:

      1. **Discover Manuscripts**: If no file path is provided in the args, use \`discover_manuscript\` to find available manuscript files.
      2. **Inspect Environment**: Use \`inspect_project\` to ensure the environment is ready and relevant tools are available.
      3. **Parse & Map**: Use \`parse_docx\` or \`parse_pdf\` on the selected manuscript, followed by \`map_sections\` to understand the document structure.
      4. **In-Depth Analysis**: Use the specialized analysis tools as needed based on the manuscript content and user focus:
         - \`analyze_methods\` for methodological skepticism and rigor.
         - \`analyze_coherence\` for logical flow and transitions.
         - \`analyze_terminology\` for consistent and precise language.
         - \`analyze_figures_tables\` for clarity and correctness of data presentation.
         - \`analyze_citations\` for citation accuracy and relevance.
      5. **Arbitration**: Use \`arbitrate_review\` to synthesize findings from different analysis steps into a coherent set of recommendations.
      6. **Output Generation**: Use \`render_outputs\` to generate the final review artifacts and \`validate_outputs\` to ensure everything is correct.

      Focus on:
      - Scientific rigor and methodological soundness.
      - Clarity and coherence of the narrative.
      - Adherence to academic standards and journal formatting.
      - Actionable feedback for the authors.

      Args (e.g., file path): ${args}
    `

const review: Command = {
  type: 'prompt',
  name: 'review',
  description: 'Review a scientific manuscript',
  progressMessage: 'reviewing manuscript',
  contentLength: 0,
  source: 'builtin',
  async getPromptForCommand(args): Promise<ContentBlockParam[]> {
    return [{ type: 'text', text: MANUSCRIPT_REVIEW_PROMPT(args) }]
  },
}

export default review
