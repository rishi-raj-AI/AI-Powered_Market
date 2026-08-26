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

  static dynamic _decode(http.Response response) {
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(body is Map ? (body['detail'] ?? 'Request failed') : 'Request failed');
    }
    return body;
  }

  static Future<String?> requestOtp(String phone) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/request-otp'), headers: await _headers(), body: jsonEncode({'phone': phone}));
    final data = _decode(r) as Map<String, dynamic>;
    return data['dev_otp'] as String?;
  }

  static Future<void> verifyOtp(String phone, String otp, String name) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/verify-otp'), headers: await _headers(), body: jsonEncode({'phone': phone, 'otp': otp, if (name.isNotEmpty) 'full_name': name}));
    final data = _decode(r) as Map<String, dynamic>;
    await saveToken(data['access_token'] as String);
  }

  static Future<UserModel> me() async {
    final r = await http.get(Uri.parse('$baseUrl/users/me'), headers: await _headers());
    return UserModel.fromJson(_decode(r));
  }

  static Future<List<Village>> villages() async {
    final r = await http.get(Uri.parse('$baseUrl/villages'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => Village.fromJson(e)).toList();
  }

  static Future<List<StoreModel>> stores([String? villageId]) async {
    final uri = Uri.parse('$baseUrl/stores').replace(queryParameters: villageId == null ? null : {'village_id': villageId});
    final r = await http.get(uri, headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => StoreModel.fromJson(e)).toList();
  }

  static Future<List<StoreProduct>> storeProducts(String storeId) async {
    final r = await http.get(Uri.parse('$baseUrl/stores/$storeId/products'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => StoreProduct.fromJson(e)).toList();
  }

  static Future<CartModel> cart() async {
    final r = await http.get(Uri.parse('$baseUrl/cart'), headers: await _headers());
    return CartModel.fromJson(_decode(r));
  }

  static Future<CartModel> addToCart(String listingId, {int quantity = 1}) async {
    final r = await http.post(Uri.parse('$baseUrl/cart/items'), headers: await _headers(), body: jsonEncode({'store_product_id': listingId, 'quantity': quantity}));
    return CartModel.fromJson(_decode(r));
  }

  static Future<CartModel> removeCartItem(String id) async {
    final r = await http.delete(Uri.parse('$baseUrl/cart/items/$id'), headers: await _headers());
    return CartModel.fromJson(_decode(r));
  }

  static Future<List<AddressModel>> addresses() async {
    final r = await http.get(Uri.parse('$baseUrl/addresses/me'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => AddressModel.fromJson(e)).toList();
  }

  static Future<AddressModel> createAddress({required String villageId, required String label, required String landmark, String? houseDetails, String? recipientName, String? phone}) async {
    final r = await http.post(Uri.parse('$baseUrl/addresses/me'), headers: await _headers(), body: jsonEncode({
      'village_id': villageId,
      'label': label,
      'recipient_name': recipientName,
      'phone': phone,
      'house_details': houseDetails,
      'landmark': landmark,
      'directions': null,
      'latitude': null,
      'longitude': null,
      'is_default': false,
    }));
    return AddressModel.fromJson(_decode(r));
  }

  static Future<OrderModel> checkout(String addressId, String paymentMethod) async {
    final r = await http.post(Uri.parse('$baseUrl/orders/checkout'), headers: await _headers(), body: jsonEncode({'address_id': addressId, 'payment_method': paymentMethod}));
    return OrderModel.fromJson(_decode(r));
  }

  static Future<List<OrderModel>> orders() async {
    final r = await http.get(Uri.parse('$baseUrl/orders/me'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => OrderModel.fromJson(e)).toList();
  }

  static Future<List<OrderModel>> merchantOrders() async {
    final r = await http.get(Uri.parse('$baseUrl/merchant/orders'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => OrderModel.fromJson(e)).toList();
  }

  static Future<OrderModel> updateMerchantOrder(String id, String status) async {
    final r = await http.patch(Uri.parse('$baseUrl/merchant/orders/$id/status'), headers: await _headers(), body: jsonEncode({'status': status}));
    return OrderModel.fromJson(_decode(r));
  }

  static Future<List<DeliveryModel>> availableDeliveries() async {
    final r = await http.get(Uri.parse('$baseUrl/delivery/available'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => DeliveryModel.fromJson(e)).toList();
  }

  static Future<List<DeliveryModel>> myDeliveries() async {
    final r = await http.get(Uri.parse('$baseUrl/delivery/me'), headers: await _headers());
    return (_decode(r) as List<dynamic>).map((e) => DeliveryModel.fromJson(e)).toList();
  }

  static Future<DeliveryModel> claimDelivery(String id) async {
    final r = await http.post(Uri.parse('$baseUrl/delivery/$id/claim'), headers: await _headers());
    return DeliveryModel.fromJson(_decode(r));
  }

  static Future<DeliveryModel> updateDelivery(String id, String status) async {
    final r = await http.patch(Uri.parse('$baseUrl/delivery/$id/status'), headers: await _headers(), body: jsonEncode({'status': status}));
    return DeliveryModel.fromJson(_decode(r));
  }
}
