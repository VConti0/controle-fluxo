import type { Auth } from 'firebase-admin/auth';

import type { AccountDirectory } from '../domain/economy';

export class FirebaseAccounts implements AccountDirectory {
  constructor(private readonly auth: Auth) {}

  async remove(uid: string): Promise<void> {
    await this.auth.deleteUser(uid);
  }
}
