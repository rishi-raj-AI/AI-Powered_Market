import 'dart:async';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/gaon_api.dart';

class RiderLiveLocation extends StatefulWidget {
  final String deliveryId;
  final bool active;

  const RiderLiveLocation({super.key, required this.deliveryId, required this.active});

  @override
  State<RiderLiveLocation> createState() => _RiderLiveLocationState();
}

class _RiderLiveLocationState extends State<RiderLiveLocation> {
  StreamSubscription<Position>? _subscription;
  DateTime? _lastSent;
  bool _sharing = false;
  bool _sending = false;
  String _message = 'Live GPS is off.';

  @override
  void didUpdateWidget(covariant RiderLiveLocation oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.active && oldWidget.active) {
      unawaited(_stop('Live GPS stopped because this delivery is no longer active.'));
    } else if (oldWidget.deliveryId != widget.deliveryId) {
      unawaited(_stop());
    }
  }

  @override
  void dispose() {
    final subscription = _subscription;
    _subscription = null;
    if (subscription != null) unawaited(subscription.cancel());
    super.dispose();
  }

  Future<bool> _ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      if (mounted) setState(() => _message = 'Turn on device location services to share live GPS.');
      return false;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied) {
      if (mounted) setState(() => _message = 'Location permission was denied.');
      return false;
    }
    if (permission == LocationPermission.deniedForever) {
      if (mounted) setState(() => _message = 'Location permission is blocked. Enable it in app settings.');
      return false;
    }
    return true;
  }

  Future<void> _start() async {
    if (!widget.active) {
      setState(() => _message = 'Live GPS is available only during an active delivery.');
      return;
    }
    if (_subscription != null || !await _ensurePermission() || !mounted) return;
    setState(() {_sharing = true;_message = 'Waiting for a fresh GPS fix…';});
    const settings = LocationSettings(accuracy: LocationAccuracy.high, distanceFilter: 8);
    _subscription = Geolocator.getPositionStream(locationSettings: settings).listen(
      _onPosition,
      onError: (Object error) {if (mounted) setState(() => _message = 'GPS update failed. $error');},
    );
  }

  Future<void> _onPosition(Position position) async {
    if (!widget.active || _sending) return;
    final now = DateTime.now().toUtc();
    final recordedAt = position.timestamp.toUtc();
    if (now.difference(recordedAt).abs() > const Duration(seconds: 30)) {
      if (mounted) setState(() => _message = 'Waiting for a fresh GPS fix…');
      return;
    }
    if (_lastSent != null && now.difference(_lastSent!) < const Duration(seconds: 8)) return;
    _sending = true;
    try {
      await GaonApi.sendDeliveryLocation(
        widget.deliveryId,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracy: position.accuracy,
        heading: position.heading.isFinite ? position.heading : null,
        speed: position.speed.isFinite && position.speed >= 0 ? position.speed : null,
        recordedAt: recordedAt,
      );
      _lastSent = now;
      if (mounted) setState(() => _message = 'Sharing live • accuracy ≈ ${position.accuracy.round()} m');
    } catch (_) {
      if (mounted) setState(() => _message = 'Could not send GPS. Retrying with the next location update.');
    } finally {
      _sending = false;
    }
  }

  Future<void> _stop([String message = 'Live GPS is off.']) async {
    final subscription = _subscription;
    _subscription = null;
    if (subscription != null) await subscription.cancel();
    _lastSent = null;
    if (mounted) setState(() {_sharing = false;_message = message;});
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start,children:[
          Row(children:[Icon(_sharing?Icons.radar:Icons.location_off_outlined),const SizedBox(width:8),const Expanded(child:Text('Live GPS',style:TextStyle(fontWeight:FontWeight.w700))),Chip(label:Text(_sharing?'Sharing':'Off'))]),
          Text(_message),const SizedBox(height:8),
          if(widget.active)(_sharing?OutlinedButton.icon(onPressed:()=>unawaited(_stop()),icon:const Icon(Icons.stop_circle_outlined),label:const Text('Stop sharing')):FilledButton.icon(onPressed:_start,icon:const Icon(Icons.my_location),label:const Text('Share live location'))),
        ]),
      ),
    );
  }
}
