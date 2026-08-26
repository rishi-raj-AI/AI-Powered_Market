import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';

class GaonApi {
  static const String baseUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000/api/v1');
  static Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();
  static Future<bool> hasToken() async => (await _prefs).getString('token') != null;
  static Future<void> saveToken(String token) async => (await _prefs).setString('token', token);
  static Future<void> logout() async => (await _prefs).remove('token');
  static Future<Map<String, String>> _headers() async {
    final token = (await _prefs).getString('token');
    return {'Content-Type': 'application/json', if (token != null) 'Authorization': 'Bearer $token'};
  }
  static Future<dynamic> _decode(http.Response response) async {
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(body is Map ? (body['detail'] ?? 'Request failed') : 'Request failed');
    }
    return body;
  }
  static Future<String?> requestOtp(String phone) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/request-otp'), headers: await _headers(), body: jsonEncode({'phone': phone}));
    final data = await _decode(r) as Map<String, dynamic>;
    return data['dev_otp'] as String?;
  }
  static Future<void> verifyOtp(String phone, String otp, String name) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/verify-otp'), headers: await _headers(), body: jsonEncode({'phone': phone, 'otp': otp, if (name.isNotEmpty) 'full_name': name}));
    final data = await _decode(r) as Map<String, dynamic>;
    await saveToken(data['access_token'] as String);
  }
  static Future<List<Village>> villages() async {
    final r = await http.get(Uri.parse('$baseUrl/villages'), headers: await _headers());
    final data = await _decode(r) as List<dynamic>;
    return data.map((e) => Village.fromJson(e as Map<String, dynamic>)).toList();
  }
  static Future<List<StoreModel>> stores([String? villageId]) async {
    final uri = Uri.parse('$baseUrl/stores').replace(queryParameters: villageId == null ? null : {'village_id': villageId});
    final r = await http.get(uri, headers: await _headers());
    final data = await _decode(r) as List<dynamic>;
    return data.map((e) => StoreModel.fromJson(e as Map<String, dynamic>)).toList();
  }
  static Future<List<StoreProduct>> storeProducts(String storeId) async {
    final r = await http.get(Uri.parse('$baseUrl/stores/$storeId/products'), headers: await _headers());
    final data = await _decode(r) as List<dynamic>;
    return data.map((e) => StoreProduct.fromJson(e as Map<String, dynamic>)).toList();
  }
  static Future<void> addToCart(String listingId) async {
    final r = await http.post(Uri.parse('$baseUrl/cart/items'), headers: await _headers(), body: jsonEncode({'store_product_id': listingId, 'quantity': 1}));
    await _decode(r);
  }
}
