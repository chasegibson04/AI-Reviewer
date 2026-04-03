import type { Command } from '../../commands.js'

const profile: Command = {
  name: 'profile',
  description: 'Inspect or set manuscript model profile aliases',
  type: 'local-jsx',
  load: () => import('./profile.js'),
}

export default profile
