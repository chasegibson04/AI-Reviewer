import type { LocalJSXCommandCall } from '../../types/command.js'
import { getCwd } from '../../utils/cwd.js'
import { detectManuscripts, detectProjectSnapshots, isOllamaRunning } from '../../utils/manuscriptDetection.js'

export const call: LocalJSXCommandCall = async (onDone, context, _args) => {
  const cwd = getCwd()
  const [ollamaOk, manuscripts, projects] = await Promise.all([
    isOllamaRunning(),
    detectManuscripts(cwd),
    detectProjectSnapshots(cwd),
  ])
  const bridgeConnected = Object.keys(context.getAppState().mcp.servers).includes(
    'review-bridge',
  )

  const lines: string[] = []
  lines.push('## Diagnose')
  lines.push(`- Ollama backend: ${ollamaOk ? 'running' : 'offline'}`)
  lines.push(`- Review bridge server: ${bridgeConnected ? 'connected' : 'disconnected'}`)
  lines.push(`- Manuscripts detected: ${manuscripts.length}`)
  lines.push(`- Projects detected: ${projects.length}`)
  lines.push('')
  lines.push('### Readiness')
  if (ollamaOk && bridgeConnected) {
    lines.push('- System is ready for local-first review workflows.')
  } else {
    lines.push('- System is not fully ready.')
    if (!ollamaOk) {
      lines.push('- Start Ollama (`ollama serve`) and confirm local models are available.')
    }
    if (!bridgeConnected) {
      lines.push(
        '- Ensure `review-bridge` MCP server is configured and Python dependencies are installed.',
      )
    }
  }

  onDone(lines.join('\n'), { display: 'system' })
  return null
}
