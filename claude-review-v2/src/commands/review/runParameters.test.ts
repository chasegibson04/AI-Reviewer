import test from 'node:test'
import assert from 'node:assert/strict'
import { parseReviewRunParameters } from './runParameters.ts'

test('uses explicit profile flag when provided', () => {
  const parsed = parseReviewRunParameters('--profile one_big_model papers/main.pdf', 'balanced_local')
  assert.equal(parsed.profile, 'one_big_model')
  assert.equal(parsed.manuscriptHint, 'papers/main.pdf')
  assert.equal(parsed.reasoningMode, 'gemma_single')
  assert.equal(parsed.reasoningModeExplicit, false)
})

test('uses inherited override when no explicit profile flag', () => {
  const parsed = parseReviewRunParameters('papers/main.pdf', 'deep_local')
  assert.equal(parsed.profile, 'deep_local')
  assert.equal(parsed.manuscriptHint, 'papers/main.pdf')
  assert.equal(parsed.reasoningMode, 'moe')
})

test('falls back to default profile when no valid selection exists', () => {
  const parsed = parseReviewRunParameters('papers/main.pdf', undefined)
  assert.equal(parsed.profile, 'local_moe')
  assert.equal(parsed.reasoningMode, 'moe')
})

test('supports explicit deep mode flag', () => {
  const parsed = parseReviewRunParameters('--profile local_moe --mode gemma papers/main.pdf', undefined)
  assert.equal(parsed.profile, 'local_moe')
  assert.equal(parsed.reasoningMode, 'gemma_single')
  assert.equal(parsed.reasoningModeExplicit, true)
  assert.equal(parsed.manuscriptHint, 'papers/main.pdf')
})
