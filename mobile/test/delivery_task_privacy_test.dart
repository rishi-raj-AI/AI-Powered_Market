import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/models/models.dart';

void main() {
  test('unassigned delivery offer parses without customer PII', () {
    final task = DeliveryTaskModel.fromJson({
      'id': 'delivery-offer',
      'order_id': 'order-offer',
      'order_number': 'GO2609020001',
      'status': 'unassigned',
      'payment_method': 'cod',
      'payment_status': 'pending',
      'total': '250.00',
      'store_name': 'Niphad Daily Needs',
      'store_landmark': 'Market Road',
      'dropoff_area': 'Niphad',
      'dropoff_distance_km': 2.5,
    });

    expect(task.customerLandmark, 'Niphad');
    expect(task.recipientName, isNull);
    expect(task.recipientPhone, isNull);
    expect(task.houseDetails, isNull);
    expect(task.customerLatitude, isNull);
    expect(task.customerLongitude, isNull);
  });
}
