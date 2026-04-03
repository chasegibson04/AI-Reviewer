import test from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_REVIEW_PROFILE,
  resolveProfileModel,
  resolveReviewProfileSelection,
  type OllamaInventory,
} from './reviewProfiles.ts'

test('default profile is local_moe', () => {
  assert.equal(DEFAULT_REVIEW_PROFILE, 'local_moe')
})

test('profile selection supports aliases and numeric choices', () => {
  assert.equal(resolveReviewProfileSelection('moe'), 'local_moe')
  assert.equal(resolveReviewProfileSelection('big'), 'one_big_model')
  assert.equal(resolveReviewProfileSelection('final'), 'full_manuscript_final_pass')
  assert.equal(resolveReviewProfileSelection('1'), 'balanced_local')
  assert.equal(resolveReviewProfileSelection('999'), null)
})

test('one_big_model prefers gemma4:26b when detected', () => {
  const inventory: OllamaInventory = {
    reachable: true,
    modelNames: ['gemma4:26b', 'qwen2.5-coder:32b'],
    hasGemma4_26b: true,
    hasGemma4_31b: false,
  }
  const resolution = resolveProfileModel('one_big_model', inventory)
  assert.equal(resolution.resolvedModel, 'gemma4:26b')
  assert.equal(resolution.fallbackUsed, false)
})

test('final-pass falls back to gemma4:31b when 26b is unavailable', () => {
  const inventory: OllamaInventory = {
    reachable: true,
    modelNames: ['gemma4:31b', 'qwen2.5-coder:32b'],
    hasGemma4_26b: false,
    hasGemma4_31b: true,
  }
  const resolution = resolveProfileModel('full_manuscript_final_pass', inventory)
  assert.equal(resolution.resolvedModel, 'gemma4:31b')
  assert.equal(resolution.fallbackUsed, true)
})

test('big-model mode picks largest detected model when Gemma is unavailable', () => {
  const inventory: OllamaInventory = {
    reachable: true,
    modelNames: ['llama3.1:8b', 'qwen2.5-coder:32b'],
    hasGemma4_26b: false,
    hasGemma4_31b: false,
  }
  const resolution = resolveProfileModel('one_big_model', inventory)
  assert.equal(resolution.resolvedModel, 'qwen2.5-coder:32b')
  assert.equal(resolution.fallbackUsed, true)
})
