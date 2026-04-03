export type ReviewProfileAlias =
  | 'quick_local'
  | 'balanced_local'
  | 'deep_local'
  | 'local_moe'
  | 'one_big_model'
  | 'full_manuscript_final_pass'
  | 'offline_strict'
  | 'llama_cpp_standard'
  | 'llama_cpp_turboquant'
  | 'gemma4_26b'
  | 'gemma4_31b'

export type ReviewProfileOption = {
  alias: ReviewProfileAlias
  label: string
  style: 'quick' | 'balanced' | 'deep' | 'moe' | 'big' | 'final-pass' | 'offline' | 'llama'
  description: string
}

export type OllamaInventory = {
  reachable: boolean
  modelNames: string[]
  hasGemma4_26b: boolean
  hasGemma4_31b: boolean
}

export type ProfileResolution = {
  profile: ReviewProfileAlias
  mode: string
  resolvedModel: string
  fallbackUsed: boolean
  notes: string[]
}

const PROFILE_OPTIONS: ReviewProfileOption[] = [
  {
    alias: 'balanced_local',
    label: 'Balanced Local',
    style: 'balanced',
    description: 'Stable everyday manuscript review on local models',
  },
  {
    alias: 'deep_local',
    label: 'Deep Local',
    style: 'deep',
    description: 'Stronger multi-stage local review for tougher manuscripts',
  },
  {
    alias: 'local_moe',
    label: 'Local MOE',
    style: 'moe',
    description: 'Default staged routing across multiple local specialist paths',
  },
  {
    alias: 'one_big_model',
    label: 'One Big Model (Gemma 4)',
    style: 'big',
    description: 'Lower-MOE brute-force review centered on a single strong model',
  },
  {
    alias: 'full_manuscript_final_pass',
    label: 'Final Pass (Gemma 4)',
    style: 'final-pass',
    description: 'Aggregated full-manuscript final judgment pass',
  },
  {
    alias: 'quick_local',
    label: 'Quick Local',
    style: 'quick',
    description: 'Fast lightweight local review',
  },
  {
    alias: 'offline_strict',
    label: 'Offline Strict',
    style: 'offline',
    description: 'Strict local/offline path with no remote fallback',
  },
  {
    alias: 'llama_cpp_standard',
    label: 'llama.cpp Standard',
    style: 'llama',
    description: 'Standard llama.cpp profile',
  },
  {
    alias: 'llama_cpp_turboquant',
    label: 'llama.cpp Turboquant',
    style: 'llama',
    description: 'Aggressive quantized llama.cpp profile',
  },
]

export const DEFAULT_REVIEW_PROFILE: ReviewProfileAlias = 'local_moe'

function normalizeModelName(name: string): string {
  return name.trim().toLowerCase()
}

function containsModelPrefix(models: string[], prefix: string): boolean {
  const target = prefix.toLowerCase()
  return models.some(model => normalizeModelName(model).startsWith(target))
}

function parseModelSizeBillions(modelName: string): number | null {
  const match = modelName.toLowerCase().match(/(\d+(?:\.\d+)?)\s*b/)
  if (!match?.[1]) return null
  return Number(match[1])
}

function largestModelByHeuristic(models: string[]): string | null {
  const withSize = models
    .map(model => ({ model, size: parseModelSizeBillions(model) }))
    .filter(item => item.size !== null) as Array<{ model: string; size: number }>

  if (withSize.length === 0) return models[0] ?? null

  withSize.sort((a, b) => b.size - a.size)
  return withSize[0]?.model ?? null
}

export async function fetchOllamaInventory(
  baseUrl = 'http://localhost:11434',
): Promise<OllamaInventory> {
  try {
    const response = await fetch(`${baseUrl.replace(/\/+$/, '')}/api/tags`, {
      signal: AbortSignal.timeout(2500),
    })

    if (!response.ok) {
      return {
        reachable: false,
        modelNames: [],
        hasGemma4_26b: false,
        hasGemma4_31b: false,
      }
    }

    const payload = (await response.json()) as {
      models?: Array<{ name?: string | null }>
    }

    const modelNames = (payload.models ?? [])
      .map(model => model.name ?? '')
      .map(name => name.trim())
      .filter(Boolean)

    return {
      reachable: true,
      hasGemma4_26b: containsModelPrefix(modelNames, 'gemma4:26b'),
      hasGemma4_31b: containsModelPrefix(modelNames, 'gemma4:31b'),
      modelNames,
    }
  } catch {
    return {
      reachable: false,
      modelNames: [],
      hasGemma4_26b: false,
      hasGemma4_31b: false,
    }
  }
}

export function getReviewProfileOptions(): ReviewProfileOption[] {
  return PROFILE_OPTIONS
}

export function describeProfileMode(profile: ReviewProfileAlias): string {
  switch (profile) {
    case 'quick_local':
      return 'quick local'
    case 'balanced_local':
      return 'balanced local'
    case 'deep_local':
      return 'deep local'
    case 'local_moe':
      return 'local MOE staged routing'
    case 'one_big_model':
      return 'single big-model review'
    case 'full_manuscript_final_pass':
      return 'full-manuscript final pass'
    case 'offline_strict':
      return 'strict offline local'
    case 'llama_cpp_standard':
      return 'llama.cpp standard'
    case 'llama_cpp_turboquant':
      return 'llama.cpp turboquant'
    case 'gemma4_26b':
      return 'gemma4 26b direct'
    case 'gemma4_31b':
      return 'gemma4 31b direct'
    default:
      return profile
  }
}

export function resolveReviewProfileSelection(input: string): ReviewProfileAlias | null {
  const value = input.trim().toLowerCase()
  if (!value) return null

  const index = Number(value)
  if (Number.isInteger(index) && index >= 1 && index <= PROFILE_OPTIONS.length) {
    return PROFILE_OPTIONS[index - 1]?.alias ?? null
  }

  const aliasMap: Record<string, ReviewProfileAlias> = {
    quick: 'quick_local',
    quick_local: 'quick_local',
    balanced: 'balanced_local',
    balanced_local: 'balanced_local',
    deep: 'deep_local',
    deep_local: 'deep_local',
    moe: 'local_moe',
    local_moe: 'local_moe',
    big: 'one_big_model',
    one_big_model: 'one_big_model',
    final: 'full_manuscript_final_pass',
    final_pass: 'full_manuscript_final_pass',
    full_manuscript_final_pass: 'full_manuscript_final_pass',
    offline: 'offline_strict',
    offline_strict: 'offline_strict',
    llama_cpp_standard: 'llama_cpp_standard',
    llama_cpp_turboquant: 'llama_cpp_turboquant',
    gemma4_26b: 'gemma4_26b',
    gemma4_31b: 'gemma4_31b',
  }

  return aliasMap[value] ?? null
}

export function resolveProfileModel(
  profile: ReviewProfileAlias,
  inventory: OllamaInventory,
  env: NodeJS.ProcessEnv = process.env,
): ProfileResolution {
  const notes: string[] = []
  const availableModels = inventory.modelNames

  if (profile === 'quick_local') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: env.OLLAMA_SMALL_MODEL || 'llama3.2:3b',
      fallbackUsed: false,
      notes,
    }
  }

  if (profile === 'balanced_local') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: env.OLLAMA_MEDIUM_MODEL || 'llama3.1:8b',
      fallbackUsed: false,
      notes,
    }
  }

  if (profile === 'deep_local') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: env.OLLAMA_BIG_MODEL || 'qwen2.5-coder:32b',
      fallbackUsed: false,
      notes,
    }
  }

  if (profile === 'local_moe') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: 'local_moe',
      fallbackUsed: false,
      notes: ['Uses staged routing rather than a single model.'],
    }
  }

  if (profile === 'one_big_model' || profile === 'full_manuscript_final_pass') {
    const preferred = profile === 'one_big_model' ? env.OLLAMA_ONE_BIG_MODEL : env.OLLAMA_FINAL_PASS_MODEL
    const envBig = env.OLLAMA_BIG_MODEL

    if (inventory.hasGemma4_26b) {
      return {
        profile,
        mode: describeProfileMode(profile),
        resolvedModel: 'gemma4:26b',
        fallbackUsed: false,
        notes: ['Gemma 4 26B detected and selected.'],
      }
    }

    if (inventory.hasGemma4_31b) {
      return {
        profile,
        mode: describeProfileMode(profile),
        resolvedModel: 'gemma4:31b',
        fallbackUsed: true,
        notes: ['Gemma 4 26B unavailable; using Gemma 4 31B.'],
      }
    }

    const preferredLower = preferred?.toLowerCase().trim()
    if (preferredLower && containsModelPrefix(availableModels, preferredLower)) {
      return {
        profile,
        mode: describeProfileMode(profile),
        resolvedModel: preferred as string,
        fallbackUsed: true,
        notes: ['Gemma 4 unavailable; using configured profile model.'],
      }
    }

    const envBigLower = envBig?.toLowerCase().trim()
    if (envBigLower && containsModelPrefix(availableModels, envBigLower)) {
      return {
        profile,
        mode: describeProfileMode(profile),
        resolvedModel: envBig as string,
        fallbackUsed: true,
        notes: ['Gemma 4 unavailable; using configured OLLAMA_BIG_MODEL.'],
      }
    }

    const heuristic = largestModelByHeuristic(availableModels)
    if (heuristic) {
      return {
        profile,
        mode: describeProfileMode(profile),
        resolvedModel: heuristic,
        fallbackUsed: true,
        notes: ['Gemma 4 unavailable; using largest detected local model.'],
      }
    }

    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: 'gemma4:26b',
      fallbackUsed: true,
      notes: ['No local inventory available; defaulting to Gemma 4 26B alias.'],
    }
  }

  if (profile === 'offline_strict') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: env.OLLAMA_BIG_MODEL || 'qwen2.5-coder:32b',
      fallbackUsed: false,
      notes,
    }
  }

  if (profile === 'llama_cpp_standard') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: 'llama_cpp_standard',
      fallbackUsed: false,
      notes,
    }
  }

  if (profile === 'llama_cpp_turboquant') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: 'llama_cpp_turboquant',
      fallbackUsed: false,
      notes,
    }
  }

  if (profile === 'gemma4_26b') {
    return {
      profile,
      mode: describeProfileMode(profile),
      resolvedModel: 'gemma4:26b',
      fallbackUsed: false,
      notes,
    }
  }

  return {
    profile,
    mode: describeProfileMode('gemma4_31b'),
    resolvedModel: 'gemma4:31b',
    fallbackUsed: false,
    notes,
  }
}

export function profileAvailabilitySummary(inventory: OllamaInventory): string {
  if (!inventory.reachable) {
    return 'Ollama backend unreachable; model inventory unavailable.'
  }

  if (inventory.modelNames.length === 0) {
    return 'Ollama reachable but no local models were reported.'
  }

  return `Ollama reachable with ${inventory.modelNames.length} model(s); Gemma4 26B: ${inventory.hasGemma4_26b ? 'yes' : 'no'}, Gemma4 31B: ${inventory.hasGemma4_31b ? 'yes' : 'no'}.`
}
