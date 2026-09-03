import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/models/models.dart';

void main() {
  test('store availability uses the backend-computed India-local state', () {
    final store = StoreModel.fromJson({
      'id': 'store-closed',
      'name': 'Night Store',
      'delivery_enabled': true,
      'is_open_now': false,
    });

    expect(store.isOpenNow, isFalse);
  });
}
