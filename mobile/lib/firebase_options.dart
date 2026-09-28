import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

/// Public Firebase identifiers are supplied at build time by the release
/// environment. They are identifiers, not server credentials.
class GaonOneFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) return _for('WEB');
    return switch (defaultTargetPlatform) {
      TargetPlatform.android => _for('ANDROID'),
      TargetPlatform.iOS => _for('IOS'),
      _ => throw UnsupportedError('Firebase Google sign-in is supported on Android and iOS only.'),
    };
  }

  static FirebaseOptions _for(String platform) {
    final apiKey = _value(platform, 'API_KEY');
    final appId = _value(platform, 'APP_ID');
    final messagingSenderId = _value(platform, 'MESSAGING_SENDER_ID');
    final projectId = _value(platform, 'PROJECT_ID');
    return FirebaseOptions(
      apiKey: apiKey,
      appId: appId,
      messagingSenderId: messagingSenderId,
      projectId: projectId,
      authDomain: platform == 'WEB' ? _value(platform, 'AUTH_DOMAIN') : null,
      iosBundleId: platform == 'IOS' ? 'in.gaonone.gaonone_mobile' : null,
    );
  }

  static String _value(String platform, String name) {
    const values = <String, String>{
      'WEB_API_KEY': String.fromEnvironment('GAONONE_FIREBASE_WEB_API_KEY'),
      'WEB_APP_ID': String.fromEnvironment('GAONONE_FIREBASE_WEB_APP_ID'),
      'WEB_MESSAGING_SENDER_ID': String.fromEnvironment('GAONONE_FIREBASE_WEB_MESSAGING_SENDER_ID'),
      'WEB_PROJECT_ID': String.fromEnvironment('GAONONE_FIREBASE_WEB_PROJECT_ID'),
      'WEB_AUTH_DOMAIN': String.fromEnvironment('GAONONE_FIREBASE_WEB_AUTH_DOMAIN'),
      'ANDROID_API_KEY': String.fromEnvironment('GAONONE_FIREBASE_ANDROID_API_KEY'),
      'ANDROID_APP_ID': String.fromEnvironment('GAONONE_FIREBASE_ANDROID_APP_ID'),
      'ANDROID_MESSAGING_SENDER_ID': String.fromEnvironment('GAONONE_FIREBASE_ANDROID_MESSAGING_SENDER_ID'),
      'ANDROID_PROJECT_ID': String.fromEnvironment('GAONONE_FIREBASE_ANDROID_PROJECT_ID'),
      'IOS_API_KEY': String.fromEnvironment('GAONONE_FIREBASE_IOS_API_KEY'),
      'IOS_APP_ID': String.fromEnvironment('GAONONE_FIREBASE_IOS_APP_ID'),
      'IOS_MESSAGING_SENDER_ID': String.fromEnvironment('GAONONE_FIREBASE_IOS_MESSAGING_SENDER_ID'),
      'IOS_PROJECT_ID': String.fromEnvironment('GAONONE_FIREBASE_IOS_PROJECT_ID'),
    };
    final value = values['${platform}_$name'] ?? '';
    if (value.isEmpty) throw StateError('Firebase $platform configuration is missing.');
    return value;
  }
}
