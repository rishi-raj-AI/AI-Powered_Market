import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/models/models.dart';

void main() {
  test('checkout quote preserves the server delivery fee and readiness', () {
    final quote = CheckoutQuoteModel.fromJson({
      'store_id': 'store-1',
      'address_id': 'address-1',
      'subtotal': '145.00',
      'delivery_fee': '37.50',
      'total': '182.50',
      'serviceable': true,
      'inventory_valid': true,
      'store_open': true,
      'checkout_ready': true,
      'blockers': <String>[],
    });

    expect(quote.deliveryFee, '37.50');
    expect(quote.total, '182.50');
    expect(quote.checkoutReady, isTrue);
  });

  test('checkout quote retains backend blockers', () {
    final quote = CheckoutQuoteModel.fromJson({
      'store_id': 'store-1',
      'address_id': 'address-1',
      'subtotal': '145.00',
      'delivery_fee': '0.00',
      'total': '145.00',
      'serviceable': false,
      'inventory_valid': true,
      'store_open': true,
      'checkout_ready': false,
      'blockers': ['This store does not deliver to the selected address'],
    });

    expect(quote.checkoutReady, isFalse);
    expect(quote.blockers, hasLength(1));
  });
}
