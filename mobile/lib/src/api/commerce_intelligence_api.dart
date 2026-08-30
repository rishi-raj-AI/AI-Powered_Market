import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'gaon_api.dart';

class CommerceIntelligenceApi {
  static Future<Map<String, String>> _headers() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static Future<Map<String, dynamic>> _get(String path) async {
    final response = await http
        .get(Uri.parse('${GaonApi.baseUrl}$path'), headers: await _headers())
        .timeout(GaonApi.timeout);
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map ? body['detail'] : null;
      throw Exception(
        detail is String ? detail : 'Request failed (${response.statusCode})',
      );
    }
    return Map<String, dynamic>.from(body as Map);
  }

  static Future<Map<String, dynamic>> preparationEstimate(String storeId) =>
      _get('/stores/$storeId/preparation-estimate');

  static String preparationCopy(Map<String, dynamic> estimate) {
    final minutes = estimate['estimated_preparation_minutes'] as int? ?? 30;
    final basis = estimate['basis'] as String?;
    final confidence = estimate['confidence'] as String? ?? 'low';
    if (basis == 'platform_fallback') return 'Usually ready in about $minutes min';
    if (confidence == 'low') return 'Estimated around $minutes min';
    return 'Typically ready in about $minutes min';
  }

  static String preparationDetail(Map<String, dynamic> estimate) {
    final samples = estimate['sample_count'] as int? ?? 0;
    final confidence = estimate['confidence'] as String? ?? 'low';
    if (samples <= 0) {
      return 'Early estimate while this store builds order history.';
    }
    return 'Based on $samples recent fulfilled orders • $confidence confidence';
  }
}
