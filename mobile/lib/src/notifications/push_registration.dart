import 'dart:async';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import '../api/gaon_api.dart';

/// Registers the signed-in handset for merchant, rider and customer alerts.
/// Backend notification history remains available when push is not configured.
class PushRegistration {
  static StreamSubscription<String>? _tokenChanges;

  static Future<void> start() async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;
    try {
      if (!await GaonApi.pushConfigured()) return;
      final messaging = FirebaseMessaging.instance;
      final permission = await messaging.requestPermission(alert: true, badge: true, sound: true);
      if (permission.authorizationStatus == AuthorizationStatus.denied) return;
      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) await GaonApi.registerPushToken(token);
      await _tokenChanges?.cancel();
      _tokenChanges = messaging.onTokenRefresh.listen((token) async {
        try { await GaonApi.registerPushToken(token); }
        catch (error) { debugPrint('Push token refresh registration failed: $error'); }
      });
    } catch (error) {
      // Never block checkout, rider delivery or sign-in because push is unavailable.
      debugPrint('Push registration unavailable: $error');
    }
  }

  static Future<void> stop() async {
    await _tokenChanges?.cancel();
    _tokenChanges = null;
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null && token.isNotEmpty) await GaonApi.unregisterPushToken(token);
    } catch (error) {
      debugPrint('Push unregister unavailable: $error');
    }
  }
}
