import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../config.dart';
import '../../domain/failures.dart';
import '../app_state.dart';
import '../l10n/strings.dart';
import 'common.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(s.settings)),
      body: ListView(
        children: [
          if (app.signedIn)
            ListTile(
              leading: const Icon(Icons.account_circle),
              title: Text(s.signedInAs),
              subtitle: Text(app.user?.email ?? app.user?.name ?? ''),
            )
          else
            ListTile(
              leading: const Icon(Icons.login),
              title: Text(s.signIn),
              subtitle: Text(s.signInWhy),
              onTap: app.serverMissing
                  ? null
                  : () async {
                      try {
                        await app.signIn();
                      } on SignInCancelled {
                        return;
                      } catch (_) {
                        if (context.mounted) showSnack(context, s.genericError);
                      }
                    },
            ),
          ListTile(
            leading: const Icon(Icons.restore),
            title: Text(s.restore),
            enabled: app.signedIn,
            onTap: () => app.restorePurchases(),
          ),
          if (app.privacyOptionsRequired)
            ListTile(
              leading: const Icon(Icons.privacy_tip_outlined),
              title: Text(s.privacyOptions),
              onTap: () => app.showPrivacyOptions(),
            ),
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: Text(s.privacyPolicy),
            onTap: () => launchUrl(Uri.parse(AppConfig.privacyPolicyUrl)),
          ),
          if (app.signedIn) ...[
            ListTile(
              leading: const Icon(Icons.logout),
              title: Text(s.signOut),
              onTap: () => app.signOut(),
            ),
            ListTile(
              leading: const Icon(Icons.delete_forever, color: Colors.redAccent),
              title: Text(s.deleteAccount, style: const TextStyle(color: Colors.redAccent)),
              onTap: () => _confirmDelete(context),
            ),
          ],
          const Divider(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text('${s.ageNotice}\n${s.coinsDisclaimer}',
                style: const TextStyle(color: Colors.white38, fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final s = S.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(s.deleteAccount),
        content: Text(s.deleteConfirm),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(s.cancel)),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(s.confirm, style: const TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      await AppScope.read(context).deleteAccount();
    } catch (_) {
      if (context.mounted) showSnack(context, s.genericError);
    }
  }
}
