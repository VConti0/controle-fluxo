// The app's catalog is the single source of truth for prices and product
// ids. Copy it next to the seed table so the deployed functions read the
// same file the app ships with.
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = join(here, '..', 'data');
mkdirSync(dataDir, { recursive: true });
copyFileSync(join(here, '..', '..', 'assets', 'data', 'catalog.json'), join(dataDir, 'catalog.json'));
console.log('copied catalog.json into functions/data');
