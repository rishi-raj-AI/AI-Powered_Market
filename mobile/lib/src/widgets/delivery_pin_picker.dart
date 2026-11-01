import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

/// A candidate is NOT a saved/confirmed address until the customer explicitly
/// taps "Confirm delivery pin". Never use the map's initial centre as a pin.
class DeliveryPinCandidate {
  const DeliveryPinCandidate({
    required this.latitude,
    required this.longitude,
    required this.source,
    this.accuracyMeters,
  });

  final double latitude;
  final double longitude;
  final String source; // gps or map_pin; persisted provenance is a later API change.
  final double? accuracyMeters;

  bool get isValid =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude >= -90 &&
      latitude <= 90 &&
      longitude >= -180 &&
      longitude <= 180 &&
      (accuracyMeters == null ||
          (accuracyMeters!.isFinite && accuracyMeters! >= 0));
}

/// The existing flutter_map renderer is a temporary map UI, not the Google
/// Maps SDK. Replace its tile provider before any production release.
/// No GPS is requested on opening the screen, and no location is continuously
/// tracked. A permission denial never fabricates a pin.
class DeliveryPinPicker extends StatefulWidget {
  const DeliveryPinPicker({
    super.key,
    this.locate,
    this.showTiles = true,
  });

  /// Injectable for deterministic widget tests without device permissions.
  final Future<DeliveryPinCandidate> Function()? locate;
  final bool showTiles;

  @override
  State<DeliveryPinPicker> createState() => _DeliveryPinPickerState();
}

class _DeliveryPinPickerState extends State<DeliveryPinPicker> {
  static const LatLng _initialMapCentre = LatLng(20.0778, 73.7898);
  final MapController _mapController = MapController();
  DeliveryPinCandidate? _candidate;
  String? _error;
  bool _locating = false;
  bool _mapReady = false;
  bool _needsLocationSettings = false;
  bool _needsAppSettings = false;

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  Future<DeliveryPinCandidate> _getGps() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const _PinLocationFailure(
        'Location services are off. Enable them or tap the map manually.',
        locationSettings: true,
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      throw const _PinLocationFailure(
        'Location access is permanently denied. Enable it in app settings, or tap the map.',
        appSettings: true,
      );
    }
    if (permission == LocationPermission.denied) {
      throw const _PinLocationFailure(
        'Location permission denied. You can still tap the map to choose a pin.',
      );
    }
    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 12),
      ),
    );
    return DeliveryPinCandidate(
      latitude: position.latitude,
      longitude: position.longitude,
      source: 'gps',
      accuracyMeters: position.accuracy,
    );
  }

  Future<void> _useGps() async {
    if (_locating) return;
    setState(() {
      _locating = true;
      _error = null;
      _needsAppSettings = false;
      _needsLocationSettings = false;
    });
    try {
      final candidate = await (widget.locate?.call() ?? _getGps());
      if (!mounted) return;
      if (!candidate.isValid) {
        throw const _PinLocationFailure('The location result is invalid. Choose a pin manually.');
      }
      setState(() => _candidate = candidate);
      if (_mapReady) {
        _mapController.move(LatLng(candidate.latitude, candidate.longitude), 17);
      }
    } on _PinLocationFailure catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _needsAppSettings = error.appSettings;
        _needsLocationSettings = error.locationSettings;
      });
    } on TimeoutException {
      if (mounted) {
        setState(() => _error = 'GPS timed out. Retry or tap the map manually.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not obtain GPS. Retry or tap the map manually.');
      }
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  void _chooseOnMap(LatLng point) {
    final candidate = DeliveryPinCandidate(
      latitude: point.latitude,
      longitude: point.longitude,
      source: 'map_pin',
    );
    if (!candidate.isValid) return;
    setState(() {
      _candidate = candidate;
      _error = null;
      _needsAppSettings = false;
      _needsLocationSettings = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final candidate = _candidate;
    return Scaffold(
      appBar: AppBar(title: const Text('Confirm delivery location')),
      body: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 8, 16, 8),
              child: Text(
                'Tap your doorstep on the map, or use GPS and adjust the pin. '
                'The starting map centre is not your delivery location.',
              ),
            ),
            Expanded(
              child: FlutterMap(
                mapController: _mapController,
                options: MapOptions(
                  initialCenter: _initialMapCentre,
                  initialZoom: 5,
                  onMapReady: () {
                    _mapReady = true;
                    if (_candidate != null) {
                      _mapController.move(
                        LatLng(_candidate!.latitude, _candidate!.longitude),
                        17,
                      );
                    }
                  },
                  onTap: (_, point) => _chooseOnMap(point),
                ),
                children: [
                  if (widget.showTiles)
                    TileLayer(
                      urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'in.gaonone.mobile',
                    ),
                  if (candidate != null)
                    MarkerLayer(
                      markers: [
                        Marker(
                          point: LatLng(candidate.latitude, candidate.longitude),
                          width: 48,
                          height: 48,
                          child: const Icon(
                            Icons.location_pin,
                            color: Colors.red,
                            size: 44,
                          ),
                        ),
                      ],
                    ),
                  if (widget.showTiles)
                    const RichAttributionWidget(
                      attributions: [
                        TextSourceAttribution('OpenStreetMap contributors'),
                      ],
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  OutlinedButton.icon(
                    onPressed: _locating ? null : _useGps,
                    icon: const Icon(Icons.my_location),
                    label: Text(_locating ? 'Finding location…' : 'Use my current location'),
                  ),
                  if (_locating) const LinearProgressIndicator(),
                  if (candidate == null)
                    const Text('No pin selected. Tap the map or use GPS.')
                  else ...[
                    Text(
                      'Selected pin: ${candidate.latitude.toStringAsFixed(5)}, '
                      '${candidate.longitude.toStringAsFixed(5)}',
                    ),
                    if (candidate.accuracyMeters != null)
                      Text('Reported GPS accuracy: ±${candidate.accuracyMeters!.round()} m'),
                    const Text('Check the entrance carefully before confirming.'),
                  ],
                  if (_error != null)
                    Text(
                      _error!,
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  if (_needsAppSettings)
                    TextButton(
                      onPressed: Geolocator.openAppSettings,
                      child: const Text('Open app settings'),
                    ),
                  if (_needsLocationSettings)
                    TextButton(
                      onPressed: Geolocator.openLocationSettings,
                      child: const Text('Open location settings'),
                    ),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: candidate != null && candidate.isValid
                        ? () => Navigator.of(context).pop(candidate)
                        : null,
                    child: const Text('Confirm delivery pin'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PinLocationFailure implements Exception {
  const _PinLocationFailure(
    this.message, {
    this.appSettings = false,
    this.locationSettings = false,
  });
  final String message;
  final bool appSettings;
  final bool locationSettings;
}
