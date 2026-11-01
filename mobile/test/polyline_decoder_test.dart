import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/utils/polyline_decoder.dart';

void main() {
  test('decodes a standard route polyline', () {
    final points = decodePolylineSafely('_p~iF~ps|U_ulLnnqC_mqNvxq`@');
    expect(points.length, 3);
    expect(points[0].latitude, closeTo(38.5, 0.00001));
    expect(points[0].longitude, closeTo(-120.2, 0.00001));
    expect(points[2].latitude, closeTo(43.252, 0.00001));
    expect(points[2].longitude, closeTo(-126.453, 0.00001));
  });

  test('malformed or truncated provider data returns no route', () {
    expect(decodePolylineSafely('_p~iF~ps|U_ulLnnqC_mqNvxq`'), isEmpty);
    expect(decodePolylineSafely('!'), isEmpty);
    expect(decodePolylineSafely('?'), isEmpty);
  });

  test('rejects out-of-range coordinates and excessive points', () {
    expect(decodePolylineSafely(List.filled(2, '_p~iF~ps|U').join()), isEmpty);
    expect(decodePolylineSafely(List.filled(2001, '??').join()), isEmpty);
  });
}
