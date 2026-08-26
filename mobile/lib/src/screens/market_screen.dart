import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';
import 'store_screen.dart';

class MarketScreen extends StatefulWidget {
  final VoidCallback onLoggedOut;

  const MarketScreen({super.key, required this.onLoggedOut});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  List<Village> villages = [];
  List<StoreModel> stores = [];
  String? selectedVillageId;
  bool loading = true;
  bool locating = false;
  bool usingLocation = false;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final loadedVillages = await GaonApi.villages();
      final loadedStores = await GaonApi.stores(selectedVillageId);
      if (!mounted) return;
      setState(() {
        villages = loadedVillages;
        stores = loadedStores;
        loading = false;
        usingLocation = false;
        error = null;
      });
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = exception.toString();
      });
    }
  }

  Future<void> useMyLocation() async {
    setState(() {
      locating = true;
      error = null;
    });
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        throw Exception('Location services are switched off on this device.');
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        throw Exception('Location permission is required to find nearby shops.');
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
      );
      final nearby = await GaonApi.nearbyStores(position.latitude, position.longitude);
      if (!mounted) return;
      setState(() {
        stores = nearby;
        selectedVillageId = null;
        usingLocation = true;
        locating = false;
      });
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        locating = false;
        error = exception.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Future<void> logout() async {
    await GaonApi.logout();
    if (!mounted) return;
    widget.onLoggedOut();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GaonOne', style: TextStyle(fontWeight: FontWeight.w900)),
        actions: [IconButton(onPressed: logout, icon: const Icon(Icons.logout))],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: usingLocation ? useMyLocation : load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    'Nearby market',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Choose your village or use GPS to find shops around you.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 14),
                  FilledButton.tonalIcon(
                    onPressed: locating ? null : useMyLocation,
                    icon: locating
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.my_location),
                    label: Text(locating ? 'Finding nearby shops…' : 'Use my current location'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selectedVillageId,
                    decoration: const InputDecoration(labelText: 'Or select village'),
                    items: villages
                        .map((village) => DropdownMenuItem(
                              value: village.id,
                              child: Text('${village.name}, ${village.district}'),
                            ))
                        .toList(),
                    onChanged: (value) {
                      setState(() {
                        selectedVillageId = value;
                        usingLocation = false;
                      });
                      load();
                    },
                  ),
                  const SizedBox(height: 18),
                  if (usingLocation)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        children: [
                          const Icon(Icons.location_on_outlined, size: 18),
                          const SizedBox(width: 6),
                          Text('${stores.length} shops found within the service radius'),
                        ],
                      ),
                    ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ),
                  ...stores.map(
                    (store) => Card(
                      child: ListTile(
                        title: Text(store.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(store.landmark ?? store.description ?? 'Local store'),
                            if (store.distanceKm != null)
                              Text('${store.distanceKm!.toStringAsFixed(1)} km away'),
                          ],
                        ),
                        trailing: Icon(store.deliveryEnabled ? Icons.delivery_dining : Icons.storefront),
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => StoreScreen(store: store)),
                        ),
                      ),
                    ),
                  ),
                  if (stores.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(child: Text('No stores found here yet. Try selecting a village.')),
                    ),
                ],
              ),
            ),
    );
  }
}
