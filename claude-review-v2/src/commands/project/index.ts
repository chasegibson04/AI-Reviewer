import type { Command } from '../../commands.js'

const project: Command = {
  name: 'project',
  description: 'Show active manuscript project status',
  type: 'local-jsx',
  load: () => import('./project.js'),
}

export default project
