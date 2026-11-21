// Enforces the dependency rule on the server code: src/domain may only use
// other domain files and Node's standard library. Firebase, Google APIs and
// the adapters live outside it. If this fails, add a port to the domain and
// implement it in src/adapters instead of importing the SDK.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const src = join(__dirname, '..', 'src');
const importsOf = (file: string) =>
  [...readFileSync(file, 'utf8').matchAll(/\bfrom\s+['"]([^'"]+)['"]|^\s*import\s+['"]([^'"]+)['"]/gm)].map(
    (m) => m[1] ?? m[2],
  );

describe('architecture', () => {
  it('domain/ depends only on domain/ and node: built-ins', () => {
    const bad: string[] = [];
    for (const f of readdirSync(join(src, 'domain'))) {
      for (const spec of importsOf(join(src, 'domain', f))) {
        const ok = spec.startsWith('node:') || (spec.startsWith('./') && !spec.includes('..'));
        if (!ok) bad.push(`src/domain/${f} imports ${spec}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it('adapters/ never import each other or index.ts', () => {
    const bad: string[] = [];
    for (const f of readdirSync(join(src, 'adapters'))) {
      for (const spec of importsOf(join(src, 'adapters', f))) {
        if (spec.startsWith('./') || spec.startsWith('../index')) bad.push(`src/adapters/${f} imports ${spec}`);
      }
    }
    expect(bad).toEqual([]);
  });
});
