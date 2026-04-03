import type { Command } from '../../commands.js'

const diagnose: Command = {
  name: 'diagnose',
  description: 'Run bridge and backend connectivity checks',
  type: 'local-jsx',
  load: () => import('./diagnose.js'),
}

export default diagnose
