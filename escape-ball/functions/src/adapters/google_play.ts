// Checks purchase tokens with the Google Play Developer API.
//
// Setup: in the Play Console, Users and permissions → invite the Cloud
// Functions service account (PROJECT_ID@appspot.gserviceaccount.com or the
// compute default account shown in the Google Cloud console) with "View
// financial data" permission. No key file is needed: the functions run as
// that account.
import { androidpublisher, auth } from '@googleapis/androidpublisher';

import type { PlayCheck, PurchaseVerifier } from '../domain/economy';

export class GooglePlayVerifier implements PurchaseVerifier {
  private readonly api = androidpublisher({
    version: 'v3',
    auth: new auth.GoogleAuth({ scopes: ['https://www.googleapis.com/auth/androidpublisher'] }),
  });

  constructor(private readonly packageName: string) {}

  async check(productId: string, token: string): Promise<PlayCheck> {
    try {
      const res = await this.api.purchases.products.get({
        packageName: this.packageName,
        productId,
        token,
      });
      // purchaseState: 0 purchased, 1 cancelled, 2 pending.
      switch (res.data.purchaseState) {
        case 0:
          return { state: 'purchased', orderId: res.data.orderId ?? null };
        case 2:
          return { state: 'pending' };
        default:
          return { state: 'invalid', reason: `state ${res.data.purchaseState}` };
      }
    } catch (e) {
      const status = (e as { code?: number }).code;
      if (status === 400 || status === 404 || status === 410) {
        return { state: 'invalid', reason: `play ${status}` };
      }
      throw e;
    }
  }
}

/**
 * Accepts tokens made by the app's FAKE_BILLING mode ("fake:<product>:<n>").
 * Only active in the emulator or when ALLOW_FAKE_PURCHASES=true is set on the
 * functions, for testing before the app is in the Play Store. Never set that
 * in production: anyone could credit coins for free.
 */
export class FakeAwareVerifier implements PurchaseVerifier {
  constructor(
    private readonly real: PurchaseVerifier,
    private readonly allowFake: boolean,
  ) {}

  async check(productId: string, token: string, consumable: boolean): Promise<PlayCheck> {
    if (token.startsWith('fake:')) {
      if (!this.allowFake) return { state: 'invalid', reason: 'fake purchases disabled' };
      if (!token.startsWith(`fake:${productId}:`)) return { state: 'invalid', reason: 'fake token mismatch' };
      return { state: 'purchased', orderId: null };
    }
    return this.real.check(productId, token, consumable);
  }
}
