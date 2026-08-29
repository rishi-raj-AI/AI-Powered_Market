import 'dart:async';

import 'package:flutter/material.dart';

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
    gpsTimer = Timer.periodic(const Duration(seconds: 5), (_) => _refreshTracking());
    routeTimer = Timer.periodic(const Duration(seconds: 30), (_) => _refreshRoute());
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
      if (mounted) setState(() {tracking = value;error = null;});
    } catch (_) {
      if (mounted && tracking == null) setState(() => error = 'Live tracking is temporarily unavailable.');
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

  @override
  Widget build(BuildContext context) {
    if (tracking == null && error == null) return const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator());
    if (error != null) return Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error));
    final data = tracking!;
    final active = data['tracking_active'] == true;
    final rider = data['rider'] as Map<String, dynamic>?;
    final age = data['rider_location_age_seconds'] as int? ?? 0;
    final stale = rider != null && age > 30;
    final routeAvailable = route?['available'] == true;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [const Icon(Icons.radar),const SizedBox(width:8),const Expanded(child:Text('Live delivery',style:TextStyle(fontWeight:FontWeight.w800))),Chip(label:Text('${data['delivery_status'] ?? 'unassigned'}'.replaceAll('_',' ')))]),
          if(active && routeAvailable && !stale) ...[
            Text('ETA ${_duration(route?['duration_seconds'])}',style:const TextStyle(fontWeight:FontWeight.w700)),
            Text('${_distance(route?['distance_meters'])} remaining'),
          ],
          if(active && stale) ...[
            const SizedBox(height:8),
            const Row(children:[Icon(Icons.warning_amber_rounded),SizedBox(width:6),Expanded(child:Text('Rider location may be delayed. ETA will resume after a fresh GPS update.'))]),
          ],
          if(active && rider != null) ...[
            const SizedBox(height:8),
            Text('Rider location received ${age}s ago'),
            if(rider['accuracy_m'] is num) Text('GPS accuracy ≈ ${(rider['accuracy_m'] as num).round()} m'),
          ] else if(active) ...[
            const SizedBox(height:8),const Text('Rider assigned. Waiting for the first live GPS update.'),
          ] else ...[
            const SizedBox(height:8),Text(data['order_status']=='delivered'?'Delivery completed. Live rider sharing has stopped for privacy.':'Live tracking starts after a rider accepts the delivery.'),
          ],
        ]),
      ),
    );
  }
}
