// Shapes of the data files the economy reads. Loading and validating them is
// an adapter's job (src/adapters/data_files.ts).

export interface CatalogItem {
  id: string;
  kind: 'ball' | 'map';
  price: 'free' | 'coins' | 'paid';
  coins?: number;
  productId?: string;
  shape?: string;
  default?: boolean;
}

export interface Catalog {
  removeAds: { productId: string };
  coinPacks: { productId: string; coins: number }[];
  items: CatalogItem[];
  bet: { minCoins: number; maxCoins: number };
}

export interface ShapeTable {
  multipliers: number[];
  /** [seed, attempt the ball escapes on] */
  seeds: [number, number][];
}

export interface SeedTables {
  rtp: number;
  /** [first, last] attempt of each guess band, inclusive. */
  bands: [number, number][];
  shapes: Record<string, ShapeTable>;
}

/** Throws if the catalog and seed tables do not fit together. */
export function validateData(catalog: Catalog, tables: SeedTables): void {
  const problems: string[] = [];
  if (!(tables.rtp > 0 && tables.rtp < 1)) problems.push(`rtp ${tables.rtp} out of (0, 1)`);
  for (const item of catalog.items) {
    if (item.kind === 'map' && (!item.shape || !tables.shapes[item.shape])) {
      problems.push(`map ${item.id} has no seed table for shape ${item.shape}`);
    }
    if (item.price === 'coins' && !(Number.isInteger(item.coins) && item.coins! > 0)) {
      problems.push(`item ${item.id} needs a positive coin price`);
    }
    if (item.price === 'paid' && !item.productId) problems.push(`item ${item.id} needs a productId`);
  }
  for (const [shape, t] of Object.entries(tables.shapes)) {
    if (t.multipliers.length !== tables.bands.length) problems.push(`${shape}: one multiplier per band`);
    if (t.seeds.length === 0) problems.push(`${shape}: empty seed table`);
  }
  if (catalog.bet.minCoins < 1 || catalog.bet.maxCoins < catalog.bet.minCoins) {
    problems.push('bet limits');
  }
  if (problems.length) throw new Error(`invalid data files:\n- ${problems.join('\n- ')}`);
}
