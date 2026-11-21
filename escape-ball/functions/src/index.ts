// Callable Cloud Functions used by the app. Every call requires a signed-in
// user; the balance can only change through these functions (see
// firestore.rules).
import { initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { setGlobalOptions } from 'firebase-functions/v2';
import { HttpsError, onCall, type CallableRequest } from 'firebase-functions/v2/https';

import { Economy, EconomyError } from './core';
import { loadCatalog, loadSeedTables } from './data';
import { FirestoreStore } from './firestore_store';
import { FakeAwareVerifier, GooglePlayVerifier } from './play';

setGlobalOptions({ region: 'southamerica-east1', maxInstances: 10 });

const PACKAGE_NAME = process.env.PACKAGE_NAME ?? 'com.vconti.escapeball';
const allowFake =
  process.env.FUNCTIONS_EMULATOR === 'true' || process.env.ALLOW_FAKE_PURCHASES === 'true';

initializeApp();
const economy = new Economy(
  new FirestoreStore(getFirestore()),
  loadCatalog(),
  loadSeedTables(),
  new FakeAwareVerifier(new GooglePlayVerifier(PACKAGE_NAME), allowFake),
);

function uidOf(req: CallableRequest): string {
  const uid = req.auth?.uid;
  if (!uid) throw new HttpsError('unauthenticated', 'sign in first');
  return uid;
}

async function run<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e) {
    if (e instanceof EconomyError) throw new HttpsError(e.code, e.message);
    if (e instanceof HttpsError) throw e;
    console.error(e);
    throw new HttpsError('internal', 'internal error');
  }
}

type Data = Record<string, unknown>;

export const getProfile = onCall((req) => run(() => economy.getProfile(uidOf(req))));

export const startRound = onCall<Data>((req) =>
  run(() => economy.startRound(uidOf(req), req.data ?? {})),
);

export const verifyPurchase = onCall<Data>((req) =>
  run(() => economy.verifyPurchase(uidOf(req), req.data ?? {})),
);

export const buyWithCoins = onCall<Data>((req) =>
  run(() => economy.buyWithCoins(uidOf(req), req.data ?? {})),
);

export const deleteAccount = onCall((req) =>
  run(async () => {
    const uid = uidOf(req);
    await economy.deleteAccount(uid);
    await getAuth().deleteUser(uid);
    return { deleted: true };
  }),
);
