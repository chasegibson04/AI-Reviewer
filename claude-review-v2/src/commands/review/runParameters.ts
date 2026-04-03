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

const DEFAULT_REVIEW_PROFILE: ReviewProfileAlias = 'local_moe'

function resolveReviewProfileSelection(input: string): ReviewProfileAlias | null {
  const value = input.trim().toLowerCase()
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

export type ReviewRunParameters = {
  profile: ReviewProfileAlias
  manuscriptHint: string
}

function parseProfileFlag(args: string): string | null {
  const profileFlag = args.match(/(?:^|\s)--profile\s+([^\s]+)/i)
  if (profileFlag?.[1]) return profileFlag[1]

  const profileInline = args.match(/(?:^|\s)profile=([^\s]+)/i)
  if (profileInline?.[1]) return profileInline[1]

  return null
}

export function parseReviewRunParameters(
  args: string,
  currentOverride: string | undefined,
): ReviewRunParameters {
  const profileInput = parseProfileFlag(args)
  const explicitProfile = profileInput
    ? resolveReviewProfileSelection(profileInput)
    : null

  const inheritedProfile = currentOverride
    ? resolveReviewProfileSelection(currentOverride)
    : null

  const profile = explicitProfile ?? inheritedProfile ?? DEFAULT_REVIEW_PROFILE

  const manuscriptHint = args
    .replace(/(?:^|\s)--profile\s+([^\s]+)/gi, ' ')
    .replace(/(?:^|\s)profile=([^\s]+)/gi, ' ')
    .trim()

  return {
    profile,
    manuscriptHint,
  }
}
