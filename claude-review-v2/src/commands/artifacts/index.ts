import type { Command } from '../../commands.js'

const artifacts: Command = {
  name: 'artifacts',
  description: 'List generated review artifacts',
  type: 'local-jsx',
  load: () => import('./artifacts.js'),
}

export default artifacts
