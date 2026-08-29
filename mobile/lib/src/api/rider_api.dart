import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'gaon_api.dart';
import '../models/models.dart';

class RiderApi {
  static Future<Map<String, String>> _headers() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static dynamic _decode(http.Response response) {
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map ? body['detail'] : null;
      throw Exception(detail is String ? detail : 'Request failed (${response.statusCode})');
    }
    return body;
  }

  static Future<Map<String, dynamic>?> presence() async {
    final response = await http.get(Uri.parse('${GaonApi.baseUrl}/delivery/presence'), headers: await _headers());
    final decoded = _decode(response);
    return decoded == null ? null : Map<String, dynamic>.from(decoded);
  }

  static Future<Map<String, dynamic>> updatePresence({required double latitude, required double longitude, required bool isOnline}) async {
    final response = await http.put(
      Uri.parse('${GaonApi.baseUrl}/delivery/presence'),
      headers: await _headers(),
      body: jsonEncode({'latitude': latitude, 'longitude': longitude, 'is_online': isOnline}),
    );
    return Map<String, dynamic>.from(_decode(response));
  }

  static Future<List<DeliveryTaskModel>> availableTasks() => GaonApi.availableDeliveryTasks();
  static Future<List<DeliveryTaskModel>> myTasks() => GaonApi.myDeliveryTasks();
  static Future<DeliveryModel> claim(String id) => GaonApi.claimDelivery(id);
  static Future<DeliveryModel> markPickedUp(String id) => GaonApi.updateDelivery(id, 'picked_up');

  static Future<DeliveryModel> fail(String id, {required String reason, String? notes}) async {
    final response = await http.post(
      Uri.parse('${GaonApi.baseUrl}/delivery/$id/fail'),
      headers: await _headers(),
      body: jsonEncode({'reason': reason, 'notes': notes}),
    );
    return DeliveryModel.fromJson(Map<String, dynamic>.from(_decode(response)));
  }

  static Future<Map<String, dynamic>> issueProofChallenge(String id) async {
    final response = await http.post(Uri.parse('${GaonApi.baseUrl}/delivery/$id/proof/challenge'), headers: await _headers());
    return Map<String, dynamic>.from(_decode(response));
  }

  static Future<Map<String, dynamic>> verifyProof(String id, {required String otp, String? recipientName, String? notes}) async {
    final response = await http.post(
      Uri.parse('${GaonApi.baseUrl}/delivery/$id/proof'),
      headers: await _headers(),
      body: jsonEncode({'otp': otp, 'recipient_name': recipientName, 'notes': notes}),
    );
    return Map<String, dynamic>.from(_decode(response));
  }

  static Future<DeliveryModel> complete(String id) async {
    final response = await http.post(Uri.parse('${GaonApi.baseUrl}/delivery/$id/complete'), headers: await _headers());
    return DeliveryModel.fromJson(Map<String, dynamic>.from(_decode(response)));
  }
}