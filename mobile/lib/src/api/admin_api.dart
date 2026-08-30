import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'gaon_api.dart';

class AdminApi {
  static Future<Map<String, String>> _headers() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    return {'Content-Type': 'application/json', if (token != null) 'Authorization': 'Bearer $token'};
  }

  static dynamic _decode(http.Response response) {
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map ? body['detail'] : null;
      throw Exception(detail is String ? detail : 'Request failed (${response.statusCode})');
    }
    return body;
  }

  static Future<Map<String, dynamic>> overview() async {
    final response = await http.get(Uri.parse('${GaonApi.baseUrl}/admin/overview'), headers: await _headers());
    return Map<String, dynamic>.from(_decode(response));
  }

  static Future<List<Map<String, dynamic>>> users() async {
    final response = await http.get(Uri.parse('${GaonApi.baseUrl}/admin/users'), headers: await _headers());
    return (_decode(response) as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  static Future<List<Map<String, dynamic>>> activeDeliveries() async {
    final response = await http.get(Uri.parse('${GaonApi.baseUrl}/admin/deliveries/active'), headers: await _headers());
    return (_decode(response) as List).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  static Future<Map<String, dynamic>> updateUserRole(String userId, {required String role, required bool isActive}) async {
    final response = await http.patch(
      Uri.parse('${GaonApi.baseUrl}/admin/users/$userId/role'),
      headers: await _headers(),
      body: jsonEncode({'role': role, 'is_active': isActive}),
    );
    return Map<String, dynamic>.from(_decode(response));
  }

  static Future<Map<String, dynamic>> autoAssign(String deliveryId, {double radiusKm = 15}) async {
    final response = await http.post(
      Uri.parse('${GaonApi.baseUrl}/admin/deliveries/$deliveryId/auto-assign'),
      headers: await _headers(),
      body: jsonEncode({'max_radius_km': radiusKm}),
    );
    return Map<String, dynamic>.from(_decode(response));
  }

  static Future<Map<String, dynamic>> unassign(String deliveryId) async {
    final response = await http.post(Uri.parse('${GaonApi.baseUrl}/admin/deliveries/$deliveryId/unassign'), headers: await _headers());
    return Map<String, dynamic>.from(_decode(response));
  }
}