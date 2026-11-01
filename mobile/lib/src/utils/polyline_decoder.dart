import 'package:latlong2/latlong.dart';

/// Decode a third-party route polyline without letting malformed responses
/// crash the live-tracking screen. A bad route hides the line, not the markers.
List<LatLng> decodePolylineSafely(String encoded) {
  final points = <LatLng>[];
  var index = 0;
  var latitude = 0;
  var longitude = 0;

  int? readDelta() {
    var shift = 0;
    var value = 0;
    while (index < encoded.length && shift <= 30) {
      final byte = encoded.codeUnitAt(index++) - 63;
      if (byte < 0 || byte > 63) return null;
      value |= (byte & 0x1f) << shift;
      if (byte < 0x20) {
        return (value & 1) != 0 ? ~(value >> 1) : value >> 1;
      }
      shift += 5;
    }
    return null;
  }

  while (index < encoded.length) {
    // Bound memory/CPU if a provider sends an unexpectedly large route.
    if (points.length >= 2000) return <LatLng>[];
    final latDelta = readDelta();
    final lngDelta = readDelta();
    if (latDelta == null || lngDelta == null) return <LatLng>[];
    latitude += latDelta;
    longitude += lngDelta;
    if (latitude.abs() > 9000000 || longitude.abs() > 18000000) {
      return <LatLng>[];
    }
    points.add(LatLng(latitude / 1e5, longitude / 1e5));
  }
  return points;
}
