import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/utils/tracking_freshness.dart';

void main() {
  test('freshness threshold includes 30 seconds, but not 31', () {
    expect(isRiderLocationStale(4, connectionLost: false), isFalse);
    expect(isRiderLocationStale(30, connectionLost: false), isFalse);
    expect(isRiderLocationStale(31, connectionLost: false), isTrue);
  });

  test('failed polling pauses cached live ETA even with a recent GPS fix', () {
    expect(isRiderLocationStale(4, connectionLost: true), isTrue);
  });

  test('missing, invalid and negative age values are treated as stale', () {
    for (final age in [null, '4', -1, double.nan, double.infinity]) {
      expect(isRiderLocationStale(age, connectionLost: false), isTrue);
    }
  });
}
