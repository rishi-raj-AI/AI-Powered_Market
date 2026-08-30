import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/commerce_intelligence_api.dart';
import '../api/gaon_api.dart';

class ForYouScreen extends StatefulWidget {
  const ForYouScreen({super.key});
  @override
  State<ForYouScreen> createState() => _ForYouScreenState();
}

class _ForYouScreenState extends State<ForYouScreen> {
  List<Map<String, dynamic>> items = [];
  bool loading = false;
  bool personalized = false;
  String? error;
  String? busy;

  Future<void> load() async {
    setState(() { loading = true; error = null; });
    try {
      if (!await Geolocator.isLocationServiceEnabled()) throw Exception('Location services are switched off. Browse Market instead.');
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) throw Exception('Location permission was not granted. Browse Market by area or landmark instead.');
      final position = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium));
      final data = await CommerceIntelligenceApi.personalizedFeed(latitude: position.latitude, longitude: position.longitude);
      if (mounted) setState(() { items = (data['items'] as List? ?? const []).map((e) => Map<String, dynamic>.from(e as Map)).toList(); personalized = data['personalized'] == true; });
    } catch (e) {
      if (mounted) setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally { if (mounted) setState(() => loading = false); }
  }

  Future<void> add(Map<String, dynamic> item) async {
    final id = item['listing_id'] as String;
    setState(() => busy = id);
    try {
      await GaonApi.addToCart(id);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${item['name']} added to cart')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))));
    } finally { if (mounted) setState(() => busy = null); }
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: load,
    child: ListView(padding: const EdgeInsets.all(16), children: [
      Text('For you nearby', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      const SizedBox(height: 6),
      Text(personalized ? 'Ranked using your delivered-order history and nearby live availability.' : 'Use location for nearby live availability. New customers are not falsely labelled as personalized.'),
      const SizedBox(height: 12),
      FilledButton.icon(onPressed: loading ? null : load, icon: const Icon(Icons.my_location), label: Text(loading ? 'Checking nearby…' : 'Use current location')),
      if (error != null) Card(child: ListTile(leading: const Icon(Icons.location_off_outlined), title: Text(error!))),
      if (!loading && items.isEmpty && error == null) const Card(child: ListTile(leading: Icon(Icons.auto_awesome_outlined), title: Text('Your nearby feed starts with location'), subtitle: Text('You can always use Market without location.'))),
      ...items.map((item) => Card(child: ListTile(
        title: Text(item['name'] as String? ?? 'Item'),
        subtitle: Text('${item['store_name']} • ${item['distance_km']} km\n${item['reason']}'),
        isThreeLine: true,
        trailing: OutlinedButton(onPressed: busy == item['listing_id'] ? null : () => add(item), child: Text(busy == item['listing_id'] ? 'Adding…' : '₹${item['price']} Add')),
      ))),
    ]),
  );
}
