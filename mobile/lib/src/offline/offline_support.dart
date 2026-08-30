import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../api/gaon_api.dart';

class CachedResult<T> {
  final T data;
  final bool fromCache;
  final DateTime? cachedAt;
  const CachedResult(this.data, {required this.fromCache, this.cachedAt});
}

class OfflineSupport {
  static final ValueNotifier<bool> degraded = ValueNotifier<bool>(false);
  static const _cachePrefix = 'offline.cache.';
  static const _telemetryKey = 'offline.telemetry.queue';

  static Future<Map<String, String>> _headers() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static Future<CachedResult<T>> cached<T>({
    required String key,
    required Future<T> Function() remote,
    required Object? Function(T value) encode,
    required T Function(Object? value) decode,
  }) async {
    Object? lastError;
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        final value = await remote();
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('$_cachePrefix$key', jsonEncode({
          'saved_at': DateTime.now().toUtc().toIso8601String(),
          'value': encode(value),
        }));
        degraded.value = false;
        await flushTelemetry();
        return CachedResult(value, fromCache: false);
      } catch (error) {
        lastError = error;
        if (attempt == 0) {
          await Future<void>.delayed(const Duration(milliseconds: 250));
        }
      }
    }

    degraded.value = true;
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_cachePrefix$key');
    if (raw != null) {
      final envelope = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      final savedAt = DateTime.tryParse('${envelope['saved_at']}');
      return CachedResult(decode(envelope['value']), fromCache: true, cachedAt: savedAt);
    }
    throw lastError ?? Exception('Network unavailable and no cached data exists.');
  }

  static Future<bool> sendPresence({
    required double latitude,
    required double longitude,
    required bool isOnline,
  }) async {
    final event = <String, dynamic>{
      'type': 'presence',
      'latitude': latitude,
      'longitude': longitude,
      'is_online': isOnline,
      'recorded_at': DateTime.now().toUtc().toIso8601String(),
    };
    try {
      await _sendEvent(event);
      degraded.value = false;
      await flushTelemetry();
      return true;
    } catch (_) {
      degraded.value = true;
      await _enqueueTelemetry(event, compactKey: 'presence');
      return false;
    }
  }

  static Future<bool> sendLocation({
    required String deliveryId,
    required double latitude,
    required double longitude,
    double? accuracy,
    double? heading,
    double? speed,
    DateTime? recordedAt,
  }) async {
    final event = <String, dynamic>{
      'type': 'location',
      'delivery_id': deliveryId,
      'latitude': latitude,
      'longitude': longitude,
      'accuracy_m': accuracy,
      'heading_deg': heading,
      'speed_mps': speed,
      'recorded_at': (recordedAt ?? DateTime.now().toUtc()).toIso8601String(),
    };
    try {
      await _sendEvent(event);
      degraded.value = false;
      await flushTelemetry();
      return true;
    } catch (_) {
      degraded.value = true;
      await _enqueueTelemetry(event, compactKey: 'location:$deliveryId');
      return false;
    }
  }

  static Future<void> _enqueueTelemetry(Map<String, dynamic> event, {required String compactKey}) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_telemetryKey);
    final queue = raw == null
        ? <Map<String, dynamic>>[]
        : (jsonDecode(raw) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    queue.removeWhere((item) => item['_compact_key'] == compactKey);
    event['_compact_key'] = compactKey;
    queue.add(event);
    if (queue.length > 40) queue.removeRange(0, queue.length - 40);
    await prefs.setString(_telemetryKey, jsonEncode(queue));
  }

  static Future<int> pendingTelemetryCount() async {
    final raw = (await SharedPreferences.getInstance()).getString(_telemetryKey);
    if (raw == null) return 0;
    return (jsonDecode(raw) as List).length;
  }

  static Future<void> flushTelemetry() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_telemetryKey);
    if (raw == null) return;
    final queue = (jsonDecode(raw) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    final remaining = <Map<String, dynamic>>[];
    for (var index = 0; index < queue.length; index++) {
      final event = queue[index];
      try {
        await _sendEvent(event);
      } catch (_) {
        remaining.addAll(queue.skip(index));
        degraded.value = true;
        break;
      }
    }
    if (remaining.isEmpty) {
      await prefs.remove(_telemetryKey);
    } else {
      await prefs.setString(_telemetryKey, jsonEncode(remaining));
    }
  }

  static Future<void> _sendEvent(Map<String, dynamic> event) async {
    final type = event['type'];
    late http.Response response;
    if (type == 'presence') {
      response = await http
          .put(
            Uri.parse('${GaonApi.baseUrl}/delivery/presence'),
            headers: await _headers(),
            body: jsonEncode({
              'latitude': event['latitude'],
              'longitude': event['longitude'],
              'is_online': event['is_online'],
            }),
          )
          .timeout(const Duration(seconds: 8));
    } else if (type == 'location') {
      response = await http
          .post(
            Uri.parse('${GaonApi.baseUrl}/delivery/${event['delivery_id']}/location'),
            headers: await _headers(),
            body: jsonEncode({
              'latitude': event['latitude'],
              'longitude': event['longitude'],
              'accuracy_m': event['accuracy_m'],
              'heading_deg': event['heading_deg'],
              'speed_mps': event['speed_mps'],
              'recorded_at': event['recorded_at'],
            }),
          )
          .timeout(const Duration(seconds: 8));
    } else {
      return;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Telemetry sync failed (${response.statusCode})');
    }
  }
}
