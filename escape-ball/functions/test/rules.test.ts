// Runs against the Firestore emulator: `npm run test:rules`.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, updateDoc } from 'firebase/firestore';
import { afterAll, beforeAll, describe, it } from 'vitest';

let env: RulesTestEnvironment;

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-escape-ball',
    firestore: { rules: readFileSync(join(__dirname, '..', '..', 'firestore.rules'), 'utf8') },
  });
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, 'users/alice'), { balance: 500, owned: [], removeAds: false });
    await setDoc(doc(db, 'users/bob'), { balance: 100, owned: [], removeAds: false });
    await setDoc(doc(db, 'purchases/abc'), { uid: 'alice', productId: 'coins_2' });
  });
});

afterAll(async () => {
  await env?.cleanup();
});

describe('firestore.rules', () => {
  it('a player can read their own profile', async () => {
    const db = env.authenticatedContext('alice').firestore();
    await assertSucceeds(getDoc(doc(db, 'users/alice')));
  });

  it("a player cannot read someone else's profile", async () => {
    const db = env.authenticatedContext('alice').firestore();
    await assertFails(getDoc(doc(db, 'users/bob')));
  });

  it('nobody can change a balance from the app', async () => {
    const db = env.authenticatedContext('alice').firestore();
    await assertFails(updateDoc(doc(db, 'users/alice'), { balance: 999999 }));
    await assertFails(setDoc(doc(db, 'users/alice'), { balance: 999999, owned: [], removeAds: true }));
    await assertFails(setDoc(doc(db, 'users/carol'), { balance: 999999, owned: [], removeAds: false }));
  });

  it('nobody can write round history or purchases from the app', async () => {
    const db = env.authenticatedContext('alice').firestore();
    await assertFails(setDoc(doc(db, 'users/alice/rounds/r1'), { payout: 1000 }));
    await assertFails(setDoc(doc(db, 'purchases/new'), { uid: 'alice' }));
    await assertFails(getDoc(doc(db, 'purchases/abc')));
  });

  it('signed-out clients can do nothing', async () => {
    const db = env.unauthenticatedContext().firestore();
    await assertFails(getDoc(doc(db, 'users/alice')));
    await assertFails(setDoc(doc(db, 'users/alice'), { balance: 1 }));
  });
});
