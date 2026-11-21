import { defineConfig } from 'vitest/config';

// Rules tests need the Firestore emulator; the default `npm test` skips them.
export default defineConfig({
  test: { include: ['test/rules.test.ts'], testTimeout: 20000 },
});
