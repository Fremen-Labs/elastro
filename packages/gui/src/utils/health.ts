export type ClusterHealth = 'green' | 'yellow' | 'red' | 'offline' | string

export function healthColor(health: ClusterHealth): string {
  switch (health) {
    case 'green':
      return 'hsl(var(--health-green))'
    case 'yellow':
      return 'hsl(var(--health-yellow))'
    case 'red':
      return 'hsl(var(--health-red))'
    case 'offline':
      return 'hsl(var(--health-offline))'
    default:
      return 'hsl(var(--muted-foreground))'
  }
}

export function healthPulse(health: ClusterHealth): boolean {
  return health === 'red' || health === 'offline'
}