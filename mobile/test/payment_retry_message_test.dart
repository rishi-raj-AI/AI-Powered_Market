import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/api/gaon_api.dart';

void main() {
  test('reconciliation holds never invite a second UPI charge', () {
    final message = paymentStartError(
      ApiException('Existing payment requires reconciliation', 409),
    );
    expect(message, contains('Do not pay again'));
    expect(message, contains('order status'));
  });

  for (final status in [502, 503]) {
    test('provider verification outage $status keeps the order pending', () {
      final message = paymentStartError(
        ApiException('Unable to verify previous payment', status),
      );
      expect(message, contains('order is saved'));
      expect(message, contains('before trying again'));
    });
  }

  test('unrelated errors keep their original detail', () {
    expect(paymentStartError(ApiException('Order not found', 404)), 'Order not found');
  });
}
