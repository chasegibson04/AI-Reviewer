import { expect, test } from 'bun:test'
import { parseUserSpecifiedModel } from './model.ts'

test('Model Alias Resolution', () => {
  expect(parseUserSpecifiedModel('quick_local')).toMatch(/llama3.2|3b/)
  expect(parseUserSpecifiedModel('deep_local')).toMatch(/qwen|32b/)
  expect(parseUserSpecifiedModel('balanced_local')).toMatch(/llama3.1|8b/)
  expect(parseUserSpecifiedModel('local_moe')).toBe('local_moe')
  expect(parseUserSpecifiedModel('one_big_model')).toMatch(/qwen|32b/)
})
