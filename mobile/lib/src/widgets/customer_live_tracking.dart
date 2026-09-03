import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/gaon_api.dart';

class CustomerLiveTracking extends StatefulWidget {
  final String orderId;
  const CustomerLiveTracking({super.key, required this.orderId});

  @override
  State<CustomerLiveTracking> createState() => _CustomerLiveTrackingState();
}

class _CustomerLiveTrackingState extends State<CustomerLiveTracking> {
  Map<String, dynamic>? tracking;
  Map<String, dynamic>? route;
  Timer? gpsTimer;
  Timer? routeTimer;
  String? error;

  @override
  void initState() {
    super.initState();
    _refreshTracking();
    _refreshRoute();
    gpsTimer =
        Timer.periodic(const Duration(seconds: 5), (_) => _refreshTracking());
    routeTimer =
        Timer.periodic(const Duration(seconds: 30), (_) => _refreshRoute());
  }

  @override
  void dispose() {
    gpsTimer?.cancel();
    routeTimer?.cancel();
    super.dispose();
  }

  Future<void> _refreshTracking() async {
    try {
      final value = await GaonApi.orderTracking(widget.orderId);
      if (mounted) {
        setState(() {
          tracking = value;
          error = null;
        });
      }
    } catch (_) {
      if (mounted && tracking == null) {
        setState(() => error = 'Live tracking is temporarily unavailable.');
      }
    }
  }

  Future<void> _refreshRoute() async {
    try {
      final value = await GaonApi.orderRoute(widget.orderId);
      if (mounted) setState(() => route = value);
    } catch (_) {}
  }

  String _duration(dynamic seconds) {
    if (seconds is! num) return '—';
    final minutes = (seconds.toDouble() / 60).round().clamp(1, 999);
    return '$minutes min';
  }

  String _distance(dynamic meters) {
    if (meters is! num) return '—';
    if (meters < 1000) return '${meters.round()} m';
    return '${(meters.toDouble() / 1000).toStringAsFixed(1)} km';
  }

  List<LatLng> _decodePolyline(String encoded) {
    final points = <LatLng>[];
    var index = 0, latitude = 0, longitude = 0;
    while (index < encoded.length) {
      var shift = 0, result = 0, byte = 0;
      do {
        byte = encoded.codeUnitAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20 && index < encoded.length);
      latitude += (result & 1) != 0 ? ~(result >> 1) : result >> 1;
      shift = 0;
      result = 0;
      do {
        byte = encoded.codeUnitAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20 && index < encoded.length);
      longitude += (result & 1) != 0 ? ~(result >> 1) : result >> 1;
      points.add(LatLng(latitude / 1e5, longitude / 1e5));
    }
    return points;
  }

  Future<void> _openRiderMap(Map<String, dynamic> rider) async {
    final uri = Uri.https('www.google.com', '/maps/search/', {
      'api': '1',
      'query': '${rider['latitude']},${rider['longitude']}',
    });
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    if (tracking == null && error == null) {
      return const Padding(
          padding: EdgeInsets.all(12), child: LinearProgressIndicator());
    }
    if (error != null) {
      return Text(error!,
          style: TextStyle(color: Theme.of(context).colorScheme.error));
    }
    final data = tracking!;
    final active = data['tracking_active'] == true;
    final rider = data['rider'] as Map<String, dynamic>?;
    final age = data['rider_location_age_seconds'] as int? ?? 0;
    final stale = rider != null && age > 30;
    final routeAvailable = route?['available'] == true;
    final store = data['store'] as Map<String, dynamic>?;
    final customer = data['customer'] as Map<String, dynamic>?;
    final markers = <Marker>[];
    void addMarker(Map<String, dynamic>? point, IconData icon, Color color) {
      final latitude = point?['latitude'];
      final longitude = point?['longitude'];
      if (latitude is num && longitude is num) {
        markers.add(Marker(
          point: LatLng(latitude.toDouble(), longitude.toDouble()),
          width: 44,
          height: 44,
          child: Icon(icon, color: color, size: 34),
        ));
      }
    }

    addMarker(store, Icons.storefront, Colors.deepOrange);
    addMarker(customer, Icons.home, Colors.green);
    if (active && rider != null) {
      addMarker(
          rider, Icons.delivery_dining, stale ? Colors.grey : Colors.blue);
    }
    final routePolyline = route?['encoded_polyline'] is String && !stale
        ? _decodePolyline(route!['encoded_polyline'] as String)
        : <LatLng>[];
    final center = markers.isNotEmpty
        ? markers.last.point
        : const LatLng(20.0778, 73.7898);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.radar),
            const SizedBox(width: 8),
            const Expanded(
                child: Text('Live delivery',
                    style: TextStyle(fontWeight: FontWeight.w800))),
            Chip(
                label: Text('${data['delivery_status'] ?? 'unassigned'}'
                    .replaceAll('_', ' ')))
          ]),
          if (active && routeAvailable && !stale) ...[
            Text('Live route estimate ${_duration(route?['duration_seconds'])}',
                style: const TextStyle(fontWeight: FontWeight.w700)),
            Text('${_distance(route?['distance_meters'])} remaining'),
          ],
          if (active && stale) ...[
            const SizedBox(height: 8),
            const Row(children: [
              Icon(Icons.warning_amber_rounded),
              SizedBox(width: 6),
              Expanded(
                  child: Text(
                      'Rider location may be delayed. ETA will resume after a fresh GPS update.'))
            ]),
          ],
          if (active && rider != null) ...[
            const SizedBox(height: 8),
            Text('Rider location received ${age}s ago'),
            if (rider['accuracy_m'] is num)
              Text('GPS accuracy ≈ ${(rider['accuracy_m'] as num).round()} m'),
            const SizedBox(height: 8),
            SizedBox(
              height: 240,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: FlutterMap(
                  options: MapOptions(initialCenter: center, initialZoom: 15),
                  children: [
                    TileLayer(
                      urlTemplate:
                          'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'in.gaonone.mobile',
                    ),
                    if (routePolyline.isNotEmpty)
                      PolylineLayer(polylines: [
                        Polyline(
                            points: routePolyline,
                            color: Colors.blue,
                            strokeWidth: 5)
                      ]),
                    MarkerLayer(markers: markers),
                    const RichAttributionWidget(
                      attributions: [
                        TextSourceAttribution('OpenStreetMap contributors')
                      ],
                    ),
                  ],
                ),
              ),
            ),
            TextButton.icon(
              onPressed: () => _openRiderMap(rider),
              icon: const Icon(Icons.navigation_outlined),
              label: const Text('Open rider location'),
            ),
          ] else if (active) ...[
            const SizedBox(height: 8),
            const Text(
                'Rider assigned. Waiting for the first live GPS update.'),
          ] else ...[
            const SizedBox(height: 8),
            Text(data['order_status'] == 'delivered'
                ? 'Delivery completed. Live rider sharing has stopped for privacy.'
                : 'Live tracking starts after a rider accepts the delivery.'),
          ],
        ]),
      ),
    );
  }
}
