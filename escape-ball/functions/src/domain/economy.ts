// The economy's rules (domain layer). Depends only on its ports below and on
// Node's standard library, never on Firebase or Google APIs, so it can be
// tested with in-memory fakes. All amounts are integer hundredths of a coin
// ("cents"); 1 coin = 100 cents = R$ 2,50.
import { createHash, randomInt } from 'node:crypto';

import type { Catalog, SeedTables } from './catalog';

export const CENTS_PER_COIN = 100;

export interface UserDoc {
  balance: number;
  owned: string[];
  removeAds: boolean;
}

export interface PurchaseDoc {
  /** Null once the account that made it was deleted. */
  uid: string | null;
  productId: string;
  store: 'play';
  orderId: string | null;
  consumable: boolean;
  /** Every account this one-time purchase was restored to. */
  grantedTo: string[];
}

export interface RoundDoc {
  shape: string;
  band: number;
  bet: number;
  seed: number;
  attempt: number;
  payout: number;
  balanceAfter: number;
}

/** One read-then-write unit of work. Reads must come before writes. */
export interface Tx {
  getUser(uid: string): Promise<UserDoc | null>;
  setUser(uid: string, doc: UserDoc): void;
  getPurchase(id: string): Promise<PurchaseDoc | null>;
  setPurchase(id: string, doc: PurchaseDoc): void;
  addRound(uid: string, round: RoundDoc): void;
}

export interface Store {
  transaction<T>(fn: (tx: Tx) => Promise<T>): Promise<T>;
  deleteUserData(uid: string): Promise<void>;
}

export type PlayCheck =
  | { state: 'purchased'; orderId: string | null }
  | { state: 'pending' }
  | { state: 'invalid'; reason: string };

/** Asks the store whether a purchase token is real and paid. */
export interface PurchaseVerifier {
  check(productId: string, token: string, consumable: boolean): Promise<PlayCheck>;
}

/** The sign-in accounts (Firebase Auth in production). */
export interface AccountDirectory {
  remove(uid: string): Promise<void>;
}

export type ErrorCode =
  | 'invalid-argument'
  | 'failed-precondition'
  | 'permission-denied'
  | 'not-found'
  | 'unavailable';

export class EconomyError extends Error {
  constructor(
    public readonly code: ErrorCode,
    message: string,
  ) {
    super(message);
  }
}

export interface Profile {
  balance: number;
  owned: string[];
  removeAds: boolean;
}

const emptyUser = (): UserDoc => ({ balance: 0, owned: [], removeAds: false });

const profileOf = (u: UserDoc): Profile => ({
  balance: u.balance,
  owned: [...u.owned].sort(),
  removeAds: u.removeAds,
});

/** Purchase tokens are long; their hash makes a safe document id. */
export const purchaseId = (token: string): string =>
  createHash('sha256').update(token).digest('hex');

export class Economy {
  constructor(
    private readonly store: Store,
    private readonly catalog: Catalog,
    private readonly tables: SeedTables,
    private readonly verifier: PurchaseVerifier,
    private readonly accounts: AccountDirectory,
    /** Picks an index in [0, n). Injected so tests can be exact. */
    private readonly pick: (n: number) => number = (n) => randomInt(n),
  ) {}

  /** Read-only: a profile document is only created when something changes. */
  async getProfile(uid: string): Promise<Profile> {
    return this.store.transaction(async (tx) => profileOf((await tx.getUser(uid)) ?? emptyUser()));
  }

  async startRound(
    uid: string,
    input: { shape?: unknown; band?: unknown; bet?: unknown },
  ): Promise<{ seed: number; attempt: number; payout: number; balance: number }> {
    const shape = input.shape;
    const band = input.band;
    const bet = input.bet;
    if (typeof shape !== 'string' || !(shape in this.tables.shapes)) {
      throw new EconomyError('invalid-argument', 'shape');
    }
    if (typeof band !== 'number' || !Number.isInteger(band) || band < 0 || band >= this.tables.bands.length) {
      throw new EconomyError('invalid-argument', 'band');
    }
    const { minCoins, maxCoins } = this.catalog.bet;
    if (
      typeof bet !== 'number' ||
      !Number.isInteger(bet) ||
      bet % CENTS_PER_COIN !== 0 ||
      bet < minCoins * CENTS_PER_COIN ||
      bet > maxCoins * CENTS_PER_COIN
    ) {
      throw new EconomyError('invalid-argument', 'bet');
    }

    const table = this.tables.shapes[shape];
    const [seed, attempt] = table.seeds[this.pick(table.seeds.length)];
    const [first, last] = this.tables.bands[band];
    const won = attempt >= first && attempt <= last;
    const payout = won ? Math.floor(bet * table.multipliers[band]) : 0;

    return this.store.transaction(async (tx) => {
      const u = (await tx.getUser(uid)) ?? emptyUser();
      if (u.balance < bet) throw new EconomyError('failed-precondition', 'insufficient-funds');
      const balance = u.balance - bet + payout;
      tx.setUser(uid, { ...u, balance });
      tx.addRound(uid, { shape, band, bet, seed, attempt, payout, balanceAfter: balance });
      return { seed, attempt, payout, balance };
    });
  }

  async verifyPurchase(uid: string, input: { productId?: unknown; purchaseToken?: unknown }): Promise<Profile> {
    const productId = input.productId;
    const token = input.purchaseToken;
    if (typeof productId !== 'string' || typeof token !== 'string' || token.length === 0 || token.length > 4096) {
      throw new EconomyError('invalid-argument', 'purchase');
    }
    const pack = this.catalog.coinPacks.find((p) => p.productId === productId);
    const item = this.catalog.items.find((i) => i.productId === productId);
    const isRemoveAds = productId === this.catalog.removeAds.productId;
    if (!pack && !item && !isRemoveAds) throw new EconomyError('invalid-argument', 'unknown product');
    const consumable = pack !== undefined;

    const check = await this.verifier.check(productId, token, consumable);
    if (check.state === 'pending') throw new EconomyError('failed-precondition', 'pending');
    if (check.state === 'invalid') throw new EconomyError('permission-denied', `invalid-purchase: ${check.reason}`);

    const id = purchaseId(token);
    return this.store.transaction(async (tx) => {
      const existing = await tx.getPurchase(id);
      const u = (await tx.getUser(uid)) ?? emptyUser();

      if (existing && existing.productId !== productId) {
        throw new EconomyError('permission-denied', 'token-product-mismatch');
      }

      if (consumable) {
        // A coin pack credits exactly once, to the account that bought it.
        if (existing) {
          if (existing.uid !== uid) throw new EconomyError('permission-denied', 'already-used');
          return profileOf(u);
        }
        const next = { ...u, balance: u.balance + pack!.coins * CENTS_PER_COIN };
        tx.setPurchase(id, {
          uid,
          productId,
          store: 'play',
          orderId: check.orderId,
          consumable: true,
          grantedTo: [uid],
        });
        tx.setUser(uid, next);
        return profileOf(next);
      }

      // One-time purchases belong to the Google account that paid, so
      // restoring them to another of the player's accounts is allowed.
      const next: UserDoc = isRemoveAds
        ? { ...u, removeAds: true }
        : { ...u, owned: u.owned.includes(item!.id) ? u.owned : [...u.owned, item!.id] };
      const grantedTo = existing ? existing.grantedTo : [];
      tx.setPurchase(id, {
        uid: existing?.uid ?? uid,
        productId,
        store: 'play',
        orderId: check.orderId,
        consumable: false,
        grantedTo: grantedTo.includes(uid) ? grantedTo : [...grantedTo, uid],
      });
      tx.setUser(uid, next);
      return profileOf(next);
    });
  }

  async buyWithCoins(uid: string, input: { itemId?: unknown }): Promise<Profile> {
    const item = this.catalog.items.find((i) => i.id === input.itemId);
    if (!item || item.price !== 'coins' || !item.coins) {
      throw new EconomyError('invalid-argument', 'item');
    }
    const cost = item.coins * CENTS_PER_COIN;
    return this.store.transaction(async (tx) => {
      const u = (await tx.getUser(uid)) ?? emptyUser();
      if (u.owned.includes(item.id)) return profileOf(u);
      if (u.balance < cost) throw new EconomyError('failed-precondition', 'insufficient-funds');
      const next = { ...u, balance: u.balance - cost, owned: [...u.owned, item.id] };
      tx.setUser(uid, next);
      return profileOf(next);
    });
  }

  /** Deletes coins, items and history, then the sign-in account itself. */
  async deleteAccount(uid: string): Promise<{ deleted: true }> {
    await this.store.deleteUserData(uid);
    await this.accounts.remove(uid);
    return { deleted: true };
  }
}
