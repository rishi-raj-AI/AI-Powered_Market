import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';
import 'gaon_api.dart';

class CustomerCheckoutApi {
  static Future<OrderModel> checkout({
    required String addressId,
    required String paymentMethod,
    required String idempotencyKey,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    final response = await http
        .post(
          Uri.parse('${GaonApi.baseUrl}/orders/checkout'),
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotencyKey,
            if (token != null) 'Authorization': 'Bearer $token',
          },
          body: jsonEncode({
            'address_id': addressId,
            'payment_method': paymentMethod,
          }),
        )
        .timeout(GaonApi.timeout);

    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map ? body['detail'] : null;
      throw Exception(detail is String ? detail : 'Checkout failed (${response.statusCode})');
    }
    return OrderModel.fromJson(Map<String, dynamic>.from(body as Map));
  }
}
