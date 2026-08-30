import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/commerce_intelligence_api.dart';

class FulfillmentRecommendationCard extends StatefulWidget {
  final String storeId;
  const FulfillmentRecommendationCard({super.key, required this.storeId});

  @override
  State<FulfillmentRecommendationCard> createState() =>
      _FulfillmentRecommendationCardState();
}

class _FulfillmentRecommendationCardState
    extends State<FulfillmentRecommendationCard> {
  Map<String, dynamic>? result;
  bool busy = false;
  String? error;
  String? selected;

  Future<Position?> _position() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw Exception('Location services are switched off.');
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw Exception('Location permission was not granted.');
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.medium,
        timeLimit: Duration(seconds: 8),
      ),
    );
  }

  Future<void> check() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final position = await _position();
      if (position == null) return;
      final next = await CommerceIntelligenceApi.fulfillmentRecommendation(
        widget.storeId,
        latitude: position.latitude,
        longitude: position.longitude,
      );
      if (!mounted) return;
      setState(() {
        result = next;
        selected = next['recommended_mode'] as String?;
      });
    } catch (exception) {
      if (mounted) {
        setState(() {
          error = '$exception'.replaceFirst('Exception: ', '');
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = result;
    final mode = current?['recommended_mode'] as String?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.local_shipping_outlined),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Delivery or pickup?',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: busy ? null : check,
                  icon: busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.my_location, size: 18),
                  label: Text(current == null ? 'Use location' : 'Recheck'),
                ),
              ],
            ),
            if (current == null && error == null)
              const Text(
                'Check your location for the best available fulfilment option.',
              ),
            if (error != null)
              Text(
                '$error You can still choose at checkout.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            if (current != null && mode != null) ...[
              const SizedBox(height: 8),
              Text(
                'Recommended: ${CommerceIntelligenceApi.fulfillmentLabel(mode)}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              Text(
                CommerceIntelligenceApi.fulfillmentDetail(current),
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: selected,
                decoration: const InputDecoration(
                  labelText: 'Fulfilment choice',
                  helperText:
                      'Preview only; checkout revalidates location and availability.',
                ),
                items: <DropdownMenuItem<String>>[
                  DropdownMenuItem(
                    value: mode,
                    child: Text(
                      '${CommerceIntelligenceApi.fulfillmentLabel(mode)} • recommended',
                    ),
                  ),
                  if (mode != 'delivery_now' &&
                      current['delivery_serviceable'] == true &&
                      current['store_open'] == true)
                    const DropdownMenuItem(
                      value: 'delivery_now',
                      child: Text('Delivery now'),
                    ),
                  if (mode != 'pickup_now' && current['store_open'] == true)
                    const DropdownMenuItem(
                      value: 'pickup_now',
                      child: Text('Pickup now'),
                    ),
                  if (mode != 'scheduled_delivery' &&
                      current['delivery_serviceable'] == true)
                    const DropdownMenuItem(
                      value: 'scheduled_delivery',
                      child: Text('Schedule delivery'),
                    ),
                  if (mode != 'scheduled_pickup')
                    const DropdownMenuItem(
                      value: 'scheduled_pickup',
                      child: Text('Schedule pickup'),
                    ),
                ],
                onChanged: (value) => setState(() => selected = value),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
