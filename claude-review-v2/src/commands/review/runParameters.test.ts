import test from 'node:test'
import assert from 'node:assert/strict'
import { parseReviewRunParameters } from './runParameters.ts'

test('uses explicit profile flag when provided', () => {
  const parsed = parseReviewRunParameters('--profile one_big_model papers/main.pdf', 'balanced_local')
  assert.equal(parsed.profile, 'one_big_model')
  assert.equal(parsed.manuscriptHint, 'papers/main.pdf')
})

test('uses inherited override when no explicit profile flag', () => {
  const parsed = parseReviewRunParameters('papers/main.pdf', 'deep_local')
  assert.equal(parsed.profile, 'deep_local')
  assert.equal(parsed.manuscriptHint, 'papers/main.pdf')
})

test('falls back to default profile when no valid selection exists', () => {
  const parsed = parseReviewRunParameters('papers/main.pdf', undefined)
  assert.equal(parsed.profile, 'local_moe')
})
