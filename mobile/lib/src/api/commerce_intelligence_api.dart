import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'gaon_api.dart';

class CommerceIntelligenceApi {
  static Future<Map<String, String>> _headers() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    return {'Content-Type': 'application/json', if (token != null) 'Authorization': 'Bearer $token'};
  }

  static Future<dynamic> _getAny(String path) async {
    final response = await http.get(Uri.parse('${GaonApi.baseUrl}$path'), headers: await _headers()).timeout(GaonApi.timeout);
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map ? body['detail'] : null;
      throw Exception(detail is String ? detail : 'Request failed (${response.statusCode})');
    }
    return body;
  }

  static Future<Map<String, dynamic>> _get(String path) async => Map<String, dynamic>.from(await _getAny(path) as Map);
  static Future<Map<String, dynamic>> preparationEstimate(String storeId) => _get('/stores/$storeId/preparation-estimate');
  static Future<List<Map<String, dynamic>>> basketRecommendations() async { final data = await _get('/cart/recommendations'); return (data['items'] as List? ?? const []).map((item) => Map<String, dynamic>.from(item as Map)).toList(); }
  static Future<Map<String, dynamic>> personalizedFeed({required double latitude, required double longitude}) { final query = Uri(queryParameters: {'latitude': '$latitude', 'longitude': '$longitude', 'radius_km': '20', 'limit': '20'}).query; return _get('/discovery/for-you?$query'); }
  static Future<List<Map<String, dynamic>>> substitutions(String listingId) async { final data = await _get('/store-products/$listingId/substitutions'); return (data['items'] as List? ?? const []).map((item) => Map<String, dynamic>.from(item as Map)).toList(); }
  static Future<List<Map<String, dynamic>>> fulfillmentWindows(String storeId, String mode) async { final data = await _getAny('/stores/$storeId/fulfillment-windows?mode=$mode&days=3'); return (data as List).map((item) => Map<String, dynamic>.from(item as Map)).toList(); }
  static Future<Map<String, dynamic>> fulfillmentRecommendation(String storeId, {required double latitude, required double longitude}) { final query = Uri(queryParameters: {'latitude': '$latitude', 'longitude': '$longitude'}).query; return _get('/stores/$storeId/fulfillment-recommendation?$query'); }
  static Future<List<Map<String, dynamic>>> repeatPurchaseCadence() async { final data = await _get('/me/repeat-purchase-cadence'); return (data['items'] as List? ?? const []).map((item) => Map<String, dynamic>.from(item as Map)).toList(); }
  static Future<Map<String, dynamic>> merchantReliability(String storeId) => _get('/stores/$storeId/reliability');

  static String preparationCopy(Map<String, dynamic> estimate) { final minutes = estimate['estimated_preparation_minutes'] as int? ?? 30; final basis = estimate['basis'] as String?; final confidence = estimate['confidence'] as String? ?? 'low'; if (basis == 'platform_fallback') return 'Usually ready in about $minutes min'; if (confidence == 'low') return 'Estimated around $minutes min'; return 'Typically ready in about $minutes min'; }
  static String preparationDetail(Map<String, dynamic> estimate) { final samples = estimate['sample_count'] as int? ?? 0; final confidence = estimate['confidence'] as String? ?? 'low'; if (samples <= 0) return 'Early estimate while this store builds order history.'; return 'Based on $samples recent fulfilled orders • $confidence confidence'; }
  static String fulfillmentLabel(String mode) { switch (mode) {case 'delivery_now': return 'Delivery now';case 'pickup_now': return 'Pickup now';case 'scheduled_delivery': return 'Schedule delivery';case 'scheduled_pickup': return 'Schedule pickup';default: return 'Unavailable right now';} }
  static String fulfillmentDetail(Map<String, dynamic> result) { switch (result['recommended_mode']) {case 'delivery_now': return 'The store is open and this delivery location is serviceable.';case 'pickup_now': return 'Pickup is available now; delivery is not serviceable to this location.';case 'scheduled_delivery': return 'Delivery is serviceable, but the store is currently closed.';case 'scheduled_pickup': return 'Pickup is supported after the store reopens.';default: return 'This store cannot fulfil this location or mode right now.';} }
  static String cadenceCopy(Map<String, dynamic> item) { final cadence = ((item['cadence_days'] as num?) ?? 0).round();final since = ((item['days_since_last_purchase'] as num?) ?? 0).round();if (item['due'] == true) return 'Due again • usually every $cadence days';final remaining = (cadence - since).clamp(0, cadence);return 'Likely due in about $remaining days'; }
  static String trustLabel(Map<String, dynamic> result) { final confidence = result['confidence'] as String? ?? 'low';final score = ((result['score'] as num?) ?? 0.5).toDouble();if (confidence == 'low') return 'Limited fulfilment history';if (score >= 0.9) return 'Very consistent fulfilment';if (score >= 0.75) return 'Consistent fulfilment';if (score >= 0.6) return 'Mixed fulfilment history';return 'Fulfilment needs attention'; }
  static String trustDetail(Map<String, dynamic> result) { final samples = (result['terminal_orders'] ?? result['total_orders'] ?? 0) as int;final confidence = result['confidence'] as String? ?? 'low';if (samples < 5) return 'Only $samples completed/cancelled orders are available, so this is not a strong trust signal.';return 'Operational signal from $samples completed/cancelled orders • $confidence confidence. This is not a customer star rating.'; }
}
