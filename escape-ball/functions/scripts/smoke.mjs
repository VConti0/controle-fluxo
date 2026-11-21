// End-to-end check against the emulators (auth + firestore + functions):
//   firebase emulators:exec --only auth,firestore,functions --project demo-escape-ball "node functions/scripts/smoke.mjs"
// Signs up a user, buys coins with a FAKE_BILLING token, bets, buys a skin
// with coins and deletes the account, the same calls the app makes.
const project = 'demo-escape-ball';
const region = 'southamerica-east1';
const authUrl = 'http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake';
const fn = (name) => `http://127.0.0.1:5001/${project}/${region}/${name}`;

async function signUp() {
  const r = await fetch(authUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: `p${Date.now()}@example.com`, password: 'secret123', returnSecureToken: true }),
  });
  const j = await r.json();
  if (!j.idToken) throw new Error('signUp failed: ' + JSON.stringify(j));
  return j.idToken;
}

async function call(token, name, data = {}) {
  const r = await fetch(fn(name), {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ data }),
  });
  const j = await r.json();
  if (j.error) return { error: j.error };
  return j.result;
}

function check(cond, msg) {
  if (!cond) {
    console.error('FAIL', msg);
    process.exit(1);
  }
  console.log('ok  ', msg);
}

const anon = await call(null, 'getProfile');
check(anon.error?.status === 'UNAUTHENTICATED', 'calls without sign-in are refused');

const token = await signUp();
const p0 = await call(token, 'getProfile');
check(p0.balance === 0 && p0.owned.length === 0, 'new player starts with 0 coins');

const p1 = await call(token, 'verifyPurchase', { productId: 'coins_10', purchaseToken: 'fake:coins_10:1' });
check(p1.balance === 1000, 'buying 10 coins (R$ 25) credits 10 coins');
const p1b = await call(token, 'verifyPurchase', { productId: 'coins_10', purchaseToken: 'fake:coins_10:1' });
check(p1b.balance === 1000, 'the same purchase token does not credit twice');

const bad = await call(token, 'verifyPurchase', { productId: 'coins_800', purchaseToken: 'fake:coins_10:2' });
check(bad.error?.status === 'PERMISSION_DENIED', 'a token for another product is refused');

const r = await call(token, 'startRound', { shape: 'pentagon', band: 1, bet: 200 });
check(Number.isInteger(r.seed) && r.attempt >= 1, `round played: seed ${r.seed}, escaped on attempt ${r.attempt}`);
check(r.balance === 1000 - 200 + r.payout, `balance settles: payout ${r.payout}, balance ${r.balance}`);

const tooMuch = await call(token, 'startRound', { shape: 'pentagon', band: 1, bet: 100 * 100 + 100 });
check(tooMuch.error?.status === 'INVALID_ARGUMENT', 'bets above the limit are refused');

const before = r.balance;
const skin = await call(token, 'buyWithCoins', { itemId: 'ball_neon' });
check(skin.owned.includes('ball_neon') && skin.balance === before - 200, 'buying a skin with 2 coins');

const del = await call(token, 'deleteAccount');
check(del.deleted === true, 'account deleted');
// The old ID token stays valid until it expires (up to 1 hour), but the
// account's coins and items are gone.
const after = await call(token, 'getProfile');
check(after.balance === 0 && after.owned.length === 0, 'deleted account has no coins or items left');

console.log('\nall smoke checks passed');
