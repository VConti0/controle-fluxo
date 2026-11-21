import { describe, expect, it } from 'vitest';

import {
  CENTS_PER_COIN,
  Economy,
  EconomyError,
  purchaseId,
  type PlayCheck,
  type PurchaseDoc,
  type PurchaseVerifier,
  type RoundDoc,
  type Store,
  type Tx,
  type UserDoc,
} from '../src/core';
import { loadCatalog, loadSeedTables } from '../src/data';
import { FakeAwareVerifier } from '../src/play';

/** In-memory Store with all-or-nothing transactions. */
class MemoryStore implements Store {
  users = new Map<string, UserDoc>();
  purchases = new Map<string, PurchaseDoc>();
  rounds = new Map<string, RoundDoc[]>();

  async transaction<T>(fn: (tx: Tx) => Promise<T>): Promise<T> {
    const users = new Map(this.users);
    const purchases = new Map(this.purchases);
    const rounds: [string, RoundDoc][] = [];
    const tx: Tx = {
      getUser: async (uid) => structuredClone(users.get(uid) ?? null),
      setUser: (uid, doc) => void users.set(uid, structuredClone(doc)),
      getPurchase: async (id) => structuredClone(purchases.get(id) ?? null),
      setPurchase: (id, doc) => void purchases.set(id, structuredClone(doc)),
      addRound: (uid, r) => void rounds.push([uid, r]),
    };
    const out = await fn(tx);
    this.users = users;
    this.purchases = purchases;
    for (const [uid, r] of rounds) this.rounds.set(uid, [...(this.rounds.get(uid) ?? []), r]);
    return out;
  }

  async deleteUserData(uid: string): Promise<void> {
    this.users.delete(uid);
    this.rounds.delete(uid);
    for (const [id, p] of this.purchases) {
      this.purchases.set(id, {
        ...p,
        uid: p.uid === uid ? null : p.uid,
        grantedTo: p.grantedTo.filter((g) => g !== uid),
      });
    }
  }
}

class ScriptedVerifier implements PurchaseVerifier {
  calls = 0;
  constructor(private readonly answer: PlayCheck = { state: 'purchased', orderId: 'GPA.1' }) {}
  async check(): Promise<PlayCheck> {
    this.calls++;
    return this.answer;
  }
}

const catalog = loadCatalog();
const tables = loadSeedTables();

function setup(opts: { balanceCoins?: number; verifier?: PurchaseVerifier; pick?: (n: number) => number } = {}) {
  const store = new MemoryStore();
  if (opts.balanceCoins !== undefined) {
    store.users.set('u1', { balance: opts.balanceCoins * CENTS_PER_COIN, owned: [], removeAds: false });
  }
  const economy = new Economy(store, catalog, tables, opts.verifier ?? new ScriptedVerifier(), opts.pick);
  return { store, economy };
}

async function expectCode(p: Promise<unknown>, code: string, message?: string) {
  await expect(p).rejects.toBeInstanceOf(EconomyError);
  await p.catch((e: EconomyError) => {
    expect(e.code).toBe(code);
    if (message) expect(e.message).toContain(message);
  });
}

/** Index of the first seed in a shape's table that escapes inside / outside a band. */
function seedIndex(shape: string, band: number, inside: boolean): number {
  const [first, last] = tables.bands[band];
  const i = tables.shapes[shape].seeds.findIndex(([, a]) => (a >= first && a <= last) === inside);
  expect(i).toBeGreaterThanOrEqual(0);
  return i;
}

describe('data files', () => {
  it('has a table for every map shape in the catalog', () => {
    for (const item of catalog.items.filter((i) => i.kind === 'map')) {
      expect(tables.shapes[item.shape!], item.id).toBeDefined();
      expect(tables.shapes[item.shape!].seeds.length).toBeGreaterThan(1000);
    }
  });

  it('pays back close to, and never above, the target return', () => {
    for (const [shape, t] of Object.entries(tables.shapes)) {
      tables.bands.forEach(([first, last], b) => {
        const hits = t.seeds.filter(([, a]) => a >= first && a <= last).length;
        const ret = (hits / t.seeds.length) * t.multipliers[b];
        expect(ret, `${shape} band ${b}`).toBeLessThanOrEqual(tables.rtp + 1e-9);
        expect(ret, `${shape} band ${b}`).toBeGreaterThan(tables.rtp - 0.01);
      });
    }
  });
});

describe('getProfile', () => {
  it('returns an empty profile for a new player without writing anything', async () => {
    const { economy, store } = setup();
    expect(await economy.getProfile('new')).toEqual({ balance: 0, owned: [], removeAds: false });
    expect(store.users.has('new')).toBe(false);
  });
});

describe('startRound', () => {
  it('pays the multiplier when the guess is right', async () => {
    const idx = seedIndex('pentagon', 1, true);
    const { economy, store } = setup({ balanceCoins: 10, pick: () => idx });
    const r = await economy.startRound('u1', { shape: 'pentagon', band: 1, bet: 200 });
    const expected = Math.floor(200 * tables.shapes.pentagon.multipliers[1]);
    expect(r.payout).toBe(expected);
    expect(r.balance).toBe(1000 - 200 + expected);
    expect(r.seed).toBe(tables.shapes.pentagon.seeds[idx][0]);
    expect(store.users.get('u1')!.balance).toBe(r.balance);
    expect(store.rounds.get('u1')).toHaveLength(1);
  });

  it('keeps the bet when the guess is wrong', async () => {
    const idx = seedIndex('hexagon', 0, false);
    const { economy } = setup({ balanceCoins: 10, pick: () => idx });
    const r = await economy.startRound('u1', { shape: 'hexagon', band: 0, bet: 500 });
    expect(r.payout).toBe(0);
    expect(r.balance).toBe(500);
  });

  it('refuses a bet larger than the balance and changes nothing', async () => {
    const { economy, store } = setup({ balanceCoins: 1 });
    await expectCode(
      economy.startRound('u1', { shape: 'square', band: 2, bet: 200 }),
      'failed-precondition',
      'insufficient-funds',
    );
    expect(store.users.get('u1')!.balance).toBe(100);
    expect(store.rounds.get('u1')).toBeUndefined();
  });

  it('validates shape, band and bet', async () => {
    const { economy } = setup({ balanceCoins: 1000 });
    await expectCode(economy.startRound('u1', { shape: 'circle', band: 0, bet: 100 }), 'invalid-argument');
    await expectCode(economy.startRound('u1', { shape: 'square', band: 5, bet: 100 }), 'invalid-argument');
    await expectCode(economy.startRound('u1', { shape: 'square', band: 1.5, bet: 100 }), 'invalid-argument');
    await expectCode(economy.startRound('u1', { shape: 'square', band: 0, bet: 150 }), 'invalid-argument');
    await expectCode(economy.startRound('u1', { shape: 'square', band: 0, bet: 0 }), 'invalid-argument');
    await expectCode(economy.startRound('u1', { shape: 'square', band: 0, bet: -100 }), 'invalid-argument');
    const max = catalog.bet.maxCoins * CENTS_PER_COIN;
    await expectCode(economy.startRound('u1', { shape: 'square', band: 0, bet: max + 100 }), 'invalid-argument');
  });

  it('a player who never bought anything has no balance to bet', async () => {
    const { economy } = setup();
    await expectCode(economy.startRound('nobody', { shape: 'square', band: 0, bet: 100 }), 'failed-precondition');
  });
});

describe('verifyPurchase', () => {
  it('credits a coin pack once per token', async () => {
    const { economy, store } = setup({ balanceCoins: 0 });
    const p1 = await economy.verifyPurchase('u1', { productId: 'coins_10', purchaseToken: 'tok-A' });
    expect(p1.balance).toBe(10 * CENTS_PER_COIN);
    const p2 = await economy.verifyPurchase('u1', { productId: 'coins_10', purchaseToken: 'tok-A' });
    expect(p2.balance).toBe(10 * CENTS_PER_COIN);
    expect(store.purchases.get(purchaseId('tok-A'))!.orderId).toBe('GPA.1');
  });

  it('every coin pack is worth R$ 2,50 per coin', async () => {
    const { economy } = setup({ balanceCoins: 0 });
    let total = 0;
    for (const [i, p] of catalog.coinPacks.entries()) {
      const prof = await economy.verifyPurchase('u1', { productId: p.productId, purchaseToken: `t${i}` });
      total += p.coins;
      expect(prof.balance).toBe(total * CENTS_PER_COIN);
    }
    expect(total).toBe(2 + 4 + 10 + 20 + 40 + 100 + 200 + 400 + 800);
  });

  it('a coin pack token cannot be redeemed by another account', async () => {
    const { economy } = setup({ balanceCoins: 0 });
    await economy.verifyPurchase('u1', { productId: 'coins_2', purchaseToken: 'tok-B' });
    await expectCode(
      economy.verifyPurchase('u2', { productId: 'coins_2', purchaseToken: 'tok-B' }),
      'permission-denied',
      'already-used',
    );
  });

  it('a token cannot be replayed for a different product', async () => {
    const { economy } = setup({ balanceCoins: 0 });
    await economy.verifyPurchase('u1', { productId: 'coins_2', purchaseToken: 'tok-C' });
    await expectCode(
      economy.verifyPurchase('u1', { productId: 'coins_800', purchaseToken: 'tok-C' }),
      'permission-denied',
    );
  });

  it('rejects tokens the store does not confirm, and pending payments', async () => {
    const bad = setup({ verifier: new ScriptedVerifier({ state: 'invalid', reason: 'play 400' }) });
    await expectCode(
      bad.economy.verifyPurchase('u1', { productId: 'coins_2', purchaseToken: 'x' }),
      'permission-denied',
    );
    expect(bad.store.users.size).toBe(0);
    const pending = setup({ verifier: new ScriptedVerifier({ state: 'pending' }) });
    await expectCode(
      pending.economy.verifyPurchase('u1', { productId: 'coins_2', purchaseToken: 'y' }),
      'failed-precondition',
      'pending',
    );
  });

  it('rejects unknown products without asking the store', async () => {
    const v = new ScriptedVerifier();
    const { economy } = setup({ verifier: v });
    await expectCode(economy.verifyPurchase('u1', { productId: 'free_money', purchaseToken: 'z' }), 'invalid-argument');
    expect(v.calls).toBe(0);
  });

  it('unlocks remove-ads and paid skins, and restores them to a second account', async () => {
    const { economy, store } = setup({ balanceCoins: 0 });
    expect((await economy.verifyPurchase('u1', { productId: 'remove_ads', purchaseToken: 'ra' })).removeAds).toBe(true);
    expect((await economy.verifyPurchase('u1', { productId: 'ball_fire', purchaseToken: 'bf' })).owned).toEqual([
      'ball_fire',
    ]);
    const restored = await economy.verifyPurchase('u2', { productId: 'ball_fire', purchaseToken: 'bf' });
    expect(restored.owned).toEqual(['ball_fire']);
    expect(store.purchases.get(purchaseId('bf'))!.grantedTo).toEqual(['u1', 'u2']);
  });
});

describe('fake purchases (FAKE_BILLING builds)', () => {
  it('are refused unless explicitly allowed', async () => {
    const real = new ScriptedVerifier();
    const off = new FakeAwareVerifier(real, false);
    expect((await off.check('coins_2', 'fake:coins_2:1', true)).state).toBe('invalid');
    const on = new FakeAwareVerifier(real, true);
    expect((await on.check('coins_2', 'fake:coins_2:1', true)).state).toBe('purchased');
    expect((await on.check('coins_800', 'fake:coins_2:1', true)).state).toBe('invalid');
    expect(real.calls).toBe(0);
    await on.check('coins_2', 'real-token', true);
    expect(real.calls).toBe(1);
  });
});

describe('buyWithCoins', () => {
  it('debits the price and adds the item once', async () => {
    const { economy } = setup({ balanceCoins: 10 });
    const p = await economy.buyWithCoins('u1', { itemId: 'map_square' });
    expect(p.owned).toEqual(['map_square']);
    expect(p.balance).toBe(600);
    const again = await economy.buyWithCoins('u1', { itemId: 'map_square' });
    expect(again.balance).toBe(600);
  });

  it('refuses paid-only items, free items and unaffordable ones', async () => {
    const { economy } = setup({ balanceCoins: 3 });
    await expectCode(economy.buyWithCoins('u1', { itemId: 'ball_fire' }), 'invalid-argument');
    await expectCode(economy.buyWithCoins('u1', { itemId: 'ball_white' }), 'invalid-argument');
    await expectCode(economy.buyWithCoins('u1', { itemId: 'map_octagon' }), 'failed-precondition');
  });
});

describe('deleteAccount', () => {
  it('removes the profile and history but keeps purchase records', async () => {
    const { economy, store } = setup({ balanceCoins: 5 });
    await economy.verifyPurchase('u1', { productId: 'coins_2', purchaseToken: 'del' });
    await economy.startRound('u1', { shape: 'pentagon', band: 0, bet: 100 });
    await economy.deleteAccount('u1');
    expect(store.users.has('u1')).toBe(false);
    expect(store.rounds.has('u1')).toBe(false);
    const rec = store.purchases.get(purchaseId('del'))!;
    expect(rec.uid).toBeNull();
    // The token still cannot be credited again.
    await expectCode(economy.verifyPurchase('u9', { productId: 'coins_2', purchaseToken: 'del' }), 'permission-denied');
  });
});
