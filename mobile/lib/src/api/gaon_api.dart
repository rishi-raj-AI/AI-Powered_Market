import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:razorpay_flutter/razorpay_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';

class GaonApi {
  static const String baseUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000/api/v1');
  static const Duration timeout = Duration(seconds: 15);

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
      final detail = body is Map ? body['detail'] : null;
      throw Exception(detail is String ? detail : 'Request failed (${response.statusCode})');
    }
    return body;
  }

  static Future<http.Response> _get(Uri uri) async => http.get(uri, headers: await _headers()).timeout(timeout);
  static Future<http.Response> _post(Uri uri, {Object? body}) async => http.post(uri, headers: await _headers(), body: body).timeout(timeout);
  static Future<http.Response> _patch(Uri uri, {Object? body}) async => http.patch(uri, headers: await _headers(), body: body).timeout(timeout);
  static Future<http.Response> _delete(Uri uri) async => http.delete(uri, headers: await _headers()).timeout(timeout);

  static Future<String?> requestOtp(String phone) async {
    final r = await _post(Uri.parse('$baseUrl/auth/request-otp'), body: jsonEncode({'phone': phone}));
    final data = _decode(r) as Map<String, dynamic>;
    return data['dev_otp'] as String?;
  }

  static Future<void> verifyOtp(String phone, String otp, String name) async {
    final r = await _post(Uri.parse('$baseUrl/auth/verify-otp'), body: jsonEncode({'phone': phone, 'otp': otp, if (name.isNotEmpty) 'full_name': name}));
    final data = _decode(r) as Map<String, dynamic>;
    await saveToken(data['access_token'] as String);
  }

  static Future<UserModel> me() async {
    final r = await _get(Uri.parse('$baseUrl/users/me'));
    return UserModel.fromJson(_decode(r));
  }

  static Future<List<Village>> villages() async {
    final r = await _get(Uri.parse('$baseUrl/villages'));
    return (_decode(r) as List<dynamic>).map((e) => Village.fromJson(e)).toList();
  }

  static Future<List<StoreModel>> stores([String? villageId]) async {
    final uri = Uri.parse('$baseUrl/stores').replace(queryParameters: villageId == null ? null : {'village_id': villageId});
    final r = await _get(uri);
    return (_decode(r) as List<dynamic>).map((e) => StoreModel.fromJson(e)).toList();
  }

  static Future<List<StoreModel>> nearbyStores(double lat, double lng, {double radiusKm = 15}) async {
    final uri = Uri.parse('$baseUrl/stores/nearby').replace(queryParameters: {
      'lat': lat.toString(),
      'lng': lng.toString(),
      'radius_km': radiusKm.toString(),
    });
    final r = await _get(uri);
    return (_decode(r) as List<dynamic>).map((e) => StoreModel.fromJson(e)).toList();
  }

  static Future<List<StoreProduct>> storeProducts(String storeId) async {
    final r = await _get(Uri.parse('$baseUrl/stores/$storeId/products'));
    return (_decode(r) as List<dynamic>).map((e) => StoreProduct.fromJson(e)).toList();
  }

  static Future<CartModel> cart() async {
    final r = await _get(Uri.parse('$baseUrl/cart'));
    return CartModel.fromJson(_decode(r));
  }

  static Future<CartModel> addToCart(String listingId, {int quantity = 1}) async {
    final r = await _post(Uri.parse('$baseUrl/cart/items'), body: jsonEncode({'store_product_id': listingId, 'quantity': quantity}));
    return CartModel.fromJson(_decode(r));
  }

  static Future<CartModel> removeCartItem(String storeProductId) async {
    final r = await _delete(Uri.parse('$baseUrl/cart/items/$storeProductId'));
    return CartModel.fromJson(_decode(r));
  }

  static Future<List<AddressModel>> addresses() async {
    final r = await _get(Uri.parse('$baseUrl/addresses/me'));
    return (_decode(r) as List<dynamic>).map((e) => AddressModel.fromJson(e)).toList();
  }

  static Future<AddressModel> createAddress({
    required String villageId,
    required String label,
    required String landmark,
    String? houseDetails,
    String? recipientName,
    String? phone,
    double? latitude,
    double? longitude,
    String? directions,
    bool isDefault = false,
  }) async {
    final r = await _post(Uri.parse('$baseUrl/addresses/me'), body: jsonEncode({
      'village_id': villageId,
      'label': label,
      'recipient_name': recipientName,
      'phone': phone,
      'house_details': houseDetails,
      'landmark': landmark,
      'directions': directions,
      'latitude': latitude,
      'longitude': longitude,
      'is_default': isDefault,
    }));
    return AddressModel.fromJson(_decode(r));
  }

  static Future<OrderModel> checkout(String addressId, String paymentMethod) async {
    final r = await _post(Uri.parse('$baseUrl/orders/checkout'), body: jsonEncode({'address_id': addressId, 'payment_method': paymentMethod}));
    return OrderModel.fromJson(_decode(r));
  }

  static Future<List<OrderModel>> orders() async {
    final r = await _get(Uri.parse('$baseUrl/orders/me'));
    return (_decode(r) as List<dynamic>).map((e) => OrderModel.fromJson(e)).toList();
  }

  static Future<PaymentConfigModel> paymentConfig() async {
    final r = await _get(Uri.parse('$baseUrl/payments/config'));
    return PaymentConfigModel.fromJson(_decode(r));
  }

  static Future<PaymentIntentModel> paymentIntent(String orderId) async {
    final r = await _post(Uri.parse('$baseUrl/payments/orders/$orderId/intent'));
    return PaymentIntentModel.fromJson(_decode(r));
  }

  static Future<void> verifyOnlinePayment({
    required String paymentAttemptId,
    required String paymentId,
    required String signature,
  }) async {
    final r = await _post(Uri.parse('$baseUrl/payments/verify'), body: jsonEncode({
      'payment_attempt_id': paymentAttemptId,
      'razorpay_payment_id': paymentId,
      'razorpay_signature': signature,
    }));
    _decode(r);
  }

  static Future<bool> openRazorpayCheckout(OrderModel order) async {
    final config = await paymentConfig();
    if (!config.enabled || config.keyId == null) {
      throw Exception('Online payments are not configured yet. Use cash on delivery for the pilot.');
    }
    final intent = await paymentIntent(order.id);
    final customer = await me();
    final completer = Completer<bool>();
    final razorpay = Razorpay();

    Future<void> completeSuccess(PaymentSuccessResponse response) async {
      try {
        final paymentId = response.paymentId;
        final signature = response.signature;
        if (paymentId == null || signature == null) {
          throw Exception('Payment confirmation was incomplete.');
        }
        await verifyOnlinePayment(
          paymentAttemptId: intent.paymentAttemptId,
          paymentId: paymentId,
          signature: signature,
        );
        if (!completer.isCompleted) completer.complete(true);
      } catch (_) {
        if (!completer.isCompleted) completer.complete(false);
      } finally {
        razorpay.clear();
      }
    }

    void completeFailure(PaymentFailureResponse _) {
      if (!completer.isCompleted) completer.complete(false);
      razorpay.clear();
    }

    void completeWallet(ExternalWalletResponse _) {
      if (!completer.isCompleted) completer.complete(false);
      razorpay.clear();
    }

    razorpay.on(Razorpay.EVENT_PAYMENT_SUCCESS, completeSuccess);
    razorpay.on(Razorpay.EVENT_PAYMENT_ERROR, completeFailure);
    razorpay.on(Razorpay.EVENT_EXTERNAL_WALLET, completeWallet);
    razorpay.open({
      'key': intent.keyId,
      'amount': intent.amountSubunits,
      'currency': intent.currency,
      'name': 'GaonOne',
      'description': 'Order ${order.orderNumber}',
      'order_id': intent.providerOrderId,
      'prefill': {'contact': customer.phone, 'name': customer.fullName ?? ''},
      'retry': {'enabled': true, 'max_count': 4},
      'timeout': 180,
    });
    return completer.future.timeout(const Duration(minutes: 5), onTimeout: () {
      razorpay.clear();
      return false;
    });
  }

  static Future<List<NotificationEventModel>> notifications() async {
    final r = await _get(Uri.parse('$baseUrl/notifications/me'));
    return (_decode(r) as List<dynamic>).map((e) => NotificationEventModel.fromJson(e)).toList();
  }

  static Future<List<OrderModel>> merchantOrders() async {
    final r = await _get(Uri.parse('$baseUrl/merchant/orders'));
    return (_decode(r) as List<dynamic>).map((e) => OrderModel.fromJson(e)).toList();
  }

  static Future<OrderModel> updateMerchantOrder(String id, String status) async {
    final r = await _patch(Uri.parse('$baseUrl/merchant/orders/$id/status'), body: jsonEncode({'status': status}));
    return OrderModel.fromJson(_decode(r));
  }

  static Future<List<DeliveryTaskModel>> availableDeliveryTasks() async {
    final r = await _get(Uri.parse('$baseUrl/delivery/tasks/available'));
    return (_decode(r) as List<dynamic>).map((e) => DeliveryTaskModel.fromJson(e)).toList();
  }

  static Future<List<DeliveryTaskModel>> myDeliveryTasks() async {
    final r = await _get(Uri.parse('$baseUrl/delivery/tasks/me'));
    return (_decode(r) as List<dynamic>).map((e) => DeliveryTaskModel.fromJson(e)).toList();
  }

  static Future<DeliveryModel> claimDelivery(String id) async {
    final r = await _post(Uri.parse('$baseUrl/delivery/$id/claim'));
    return DeliveryModel.fromJson(_decode(r));
  }

  static Future<DeliveryModel> updateDelivery(String id, String status) async {
    final r = await _patch(Uri.parse('$baseUrl/delivery/$id/status'), body: jsonEncode({'status': status}));
    return DeliveryModel.fromJson(_decode(r));
  }
}
