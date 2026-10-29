import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart' as google;

/// Map display only: no Places, Geocoding, Routes or extra GPS requests.
class DeliveryMap extends StatefulWidget {
  const DeliveryMap(
      {super.key,
      required this.center,
      required this.markers,
      required this.fallback,
      this.path = const []});

  final google.LatLng center;
  final Set<google.Marker> markers;
  final List<google.LatLng> path;
  final Widget fallback;

  static bool get googleEnabled =>
      !kIsWeb &&
      defaultTargetPlatform == TargetPlatform.android &&
      const bool.fromEnvironment('GAONONE_ANDROID_MAPS_ENABLED') &&
      const String.fromEnvironment('GAONONE_GOOGLE_MAPS_ANDROID_API_KEY')
          .isNotEmpty;

  @override
  State<DeliveryMap> createState() => _DeliveryMapState();
}

class _DeliveryMapState extends State<DeliveryMap> {
  bool alternative = false;

  @override
  Widget build(BuildContext context) {
    if (!DeliveryMap.googleEnabled || alternative) return widget.fallback;
    return Stack(children: [
      Positioned.fill(
          child: google.GoogleMap(
        initialCameraPosition:
            google.CameraPosition(target: widget.center, zoom: 15),
        markers: widget.markers,
        polylines: widget.path.isEmpty
            ? {}
            : {
                google.Polyline(
                    polylineId: const google.PolylineId('delivery'),
                    points: widget.path,
                    color: Colors.blue,
                    width: 5),
              },
        myLocationEnabled: false,
        myLocationButtonEnabled: false,
        mapToolbarEnabled: false,
        trafficEnabled: false,
      )),
      // SDK authorization failures do not reliably reach Dart. Keep an explicit
      // escape available even if tiles fail, Google Play services are missing,
      // or the new QA signing fingerprint has not been registered yet.
      Positioned(
          top: 8,
          left: 8,
          child: ElevatedButton(
            onPressed: () => setState(() => alternative = true),
            child: const Text('Use alternative map'),
          )),
    ]);
  }
}
