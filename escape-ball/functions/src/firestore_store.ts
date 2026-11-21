// Firestore-backed Store.
//
//   users/{uid}                 balance, owned items, removeAds
//   users/{uid}/rounds/{auto}   history of bets (deleted with the account)
//   purchases/{sha256(token)}   every store purchase seen, for idempotency
import { FieldValue, type Firestore } from 'firebase-admin/firestore';

import type { PurchaseDoc, RoundDoc, Store, Tx, UserDoc } from './core';

export class FirestoreStore implements Store {
  constructor(private readonly db: Firestore) {}

  async transaction<T>(fn: (tx: Tx) => Promise<T>): Promise<T> {
    return this.db.runTransaction(async (t) => {
      const users = this.db.collection('users');
      const purchases = this.db.collection('purchases');
      const tx: Tx = {
        getUser: async (uid) => {
          const s = await t.get(users.doc(uid));
          return s.exists ? (s.data() as UserDoc) : null;
        },
        setUser: (uid, doc) => {
          t.set(users.doc(uid), { ...doc, updatedAt: FieldValue.serverTimestamp() }, { merge: true });
        },
        getPurchase: async (id) => {
          const s = await t.get(purchases.doc(id));
          return s.exists ? (s.data() as PurchaseDoc) : null;
        },
        setPurchase: (id, doc) => {
          t.set(purchases.doc(id), { ...doc, updatedAt: FieldValue.serverTimestamp() }, { merge: true });
        },
        addRound: (uid, round: RoundDoc) => {
          t.create(users.doc(uid).collection('rounds').doc(), {
            ...round,
            at: FieldValue.serverTimestamp(),
          });
        },
      };
      return fn(tx);
    });
  }

  async deleteUserData(uid: string): Promise<void> {
    await this.db.recursiveDelete(this.db.collection('users').doc(uid));
    // Purchase records stay so a token can never be credited twice, but they
    // no longer point at the deleted account.
    const owned = await this.db.collection('purchases').where('grantedTo', 'array-contains', uid).get();
    const batch = this.db.batch();
    for (const d of owned.docs) {
      const data = d.data() as PurchaseDoc;
      batch.update(d.ref, {
        uid: data.uid === uid ? null : data.uid,
        grantedTo: FieldValue.arrayRemove(uid),
      });
    }
    await batch.commit();
  }
}
