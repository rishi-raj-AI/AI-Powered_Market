import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/commerce_intelligence_api.dart';

class FulfillmentRecommendationCard extends StatefulWidget {
  final String storeId;
  const FulfillmentRecommendationCard({super.key, required this.storeId});

  @override
  State<FulfillmentRecommendationCard> createState() => _FulfillmentRecommendationCardState();
}

class _FulfillmentRecommendationCardState extends State<FulfillmentRecommendationCard> {
  Map<String, dynamic>? result;
  bool busy = false;
  String? error;
  String? selected;

  Future<Position> _position() async {
    if (!await Geolocator.isLocationServiceEnabled()) throw Exception('Location services are switched off.');
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      throw Exception('Location permission was not granted.');
    }
    return Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium));
  }

  Future<void> check() async {
    if (busy) return;
    setState(() { busy = true; error = null; });
    try {
      final position = await _position();
      final next = await CommerceIntelligenceApi.fulfillmentRecommendation(widget.storeId, latitude: position.latitude, longitude: position.longitude);
      if (!mounted) return;
      setState(() { result = next; selected = next['recommended_mode'] as String?; });
    } catch (exception) {
      if (mounted) setState(() => error = '$exception'.replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  List<String> _options(Map<String, dynamic> current) {
    final options = <String>[];
    final open = current['store_open'] == true;
    final delivery = current['delivery_enabled'] == true;
    final pickup = current['pickup_enabled'] == true;
    final serviceable = current['delivery_serviceable'] == true;
    if (delivery && serviceable && open) options.add('delivery_now');
    if (pickup && open) options.add('pickup_now');
    if (delivery && serviceable && !open) options.add('scheduled_delivery');
    if (pickup && !open) options.add('scheduled_pickup');
    if (options.isEmpty) options.add('unavailable');
    return options;
  }

  @override
  Widget build(BuildContext context) {
    final current = result;
    final mode = current?['recommended_mode'] as String?;
    final options = current == null ? const <String>[] : _options(current);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.local_shipping_outlined),
            const SizedBox(width: 8),
            const Expanded(child: Text('Delivery or pickup?', style: TextStyle(fontWeight: FontWeight.w700))),
            OutlinedButton.icon(
              onPressed: busy ? null : check,
              icon: busy ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.my_location, size: 18),
              label: Text(current == null ? 'Use location' : 'Recheck'),
            ),
          ]),
          if (current == null && error == null) const Text('Check your location for the best available fulfilment option.'),
          if (error != null) Text('$error You can still choose at checkout.', style: Theme.of(context).textTheme.bodySmall),
          if (current != null && mode != null) ...[
            const SizedBox(height: 8),
            Text('Recommended: ${CommerceIntelligenceApi.fulfillmentLabel(mode)}', style: const TextStyle(fontWeight: FontWeight.w700)),
            Text(CommerceIntelligenceApi.fulfillmentDetail(current), style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: selected,
              decoration: const InputDecoration(labelText: 'Fulfilment choice', helperText: 'Only supported modes are shown. Checkout revalidates the final order.'),
              items: options.map((value) => DropdownMenuItem(value: value, child: Text('${CommerceIntelligenceApi.fulfillmentLabel(value)}${value == mode ? ' • recommended' : ''}'))).toList(),
              onChanged: options.length == 1 && options.first == 'unavailable' ? null : (value) => setState(() => selected = value),
            ),
          ],
        ]),
      ),
    );
  }
}
