import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../../firebase_options.dart';
import '../api/gaon_api.dart';

class FirebaseGoogleSignIn {
  static Future<void>? _googleInitialization;

  static Future<void> signInAndExchange() async {
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(options: GaonOneFirebaseOptions.currentPlatform);
    }
    await (_googleInitialization ??= GoogleSignIn.instance.initialize(
      serverClientId: _serverClientId.isEmpty ? null : _serverClientId,
    ));
    final account = await GoogleSignIn.instance.authenticate();
    final googleIdToken = account.authentication.idToken;
    if (googleIdToken == null || googleIdToken.isEmpty) {
      throw StateError('Google did not return an identity token.');
    }
    final credential = GoogleAuthProvider.credential(idToken: googleIdToken);
    final firebaseCredential = await FirebaseAuth.instance.signInWithCredential(credential);
    final firebaseIdToken = await firebaseCredential.user?.getIdToken();
    if (firebaseIdToken == null || firebaseIdToken.isEmpty) {
      throw StateError('Firebase did not return an identity token.');
    }
    await GaonApi.exchangeFirebaseIdToken(firebaseIdToken);
  }

  static Future<void> signOut() async {
    try {
      if (Firebase.apps.isNotEmpty) await FirebaseAuth.instance.signOut();
      if (_googleInitialization != null) await GoogleSignIn.instance.signOut();
    } catch (_) {
      // Local GaonOne logout must remain available if the provider is offline.
    }
  }

  static const _serverClientId = String.fromEnvironment('GAONONE_GOOGLE_SERVER_CLIENT_ID');
}
