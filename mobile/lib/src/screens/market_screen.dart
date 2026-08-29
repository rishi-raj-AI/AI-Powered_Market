import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

import '../api/gaon_api.dart';
import '../api/resilient_api.dart';
import '../models/models.dart';
import 'store_screen.dart';

class MarketScreen extends StatefulWidget {
  final VoidCallback onLoggedOut;
  const MarketScreen({super.key, required this.onLoggedOut});
  @override State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  List<Village> villages = [];
  List<StoreModel> stores = [];
  List<Map<String, dynamic>> locationSuggestions = [];
  final locationController = TextEditingController();
  Timer? locationDebounce;
  String? selectedVillageId;
  String? selectedLocationLabel;
  final String locationSessionToken = '${DateTime.now().microsecondsSinceEpoch}-${Object().hashCode}';
  bool loading = true, locating = false, searchingLocation = false, usingLocation = false, cached = false;
  DateTime? cachedAt;
  String? error;

  @override void initState() { super.initState(); load(); }

  @override void dispose() {
    locationDebounce?.cancel();
    locationController.dispose();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final villageResult = await ResilientApi.villages();
      final storeResult = await ResilientApi.stores(selectedVillageId);
      if (!mounted) return;
      setState(() {
        villages = villageResult.data;
        stores = storeResult.data;
        loading = false;
        usingLocation = false;
        cached = villageResult.fromCache || storeResult.fromCache;
        cachedAt = storeResult.cachedAt ?? villageResult.cachedAt;
        error = null;
      });
    } catch (exception) {
      if (mounted) setState(() { loading = false; error = '$exception'; });
    }
  }

  void searchLocation(String value) {
    locationDebounce?.cancel();
    final query = value.trim();
    if (query.length < 2) {
      setState(() => locationSuggestions = []);
      return;
    }
    locationDebounce = Timer(const Duration(milliseconds: 280), () => _fetchLocationSuggestions(query));
  }

  Future<void> _fetchLocationSuggestions(String query) async {
    if (mounted) setState(() { searchingLocation = true; error = null; });
    try {
      final uri = Uri.parse('${GaonApi.baseUrl}/location/autocomplete').replace(queryParameters: {
        'q': query,
        'session_token': locationSessionToken,
      });
      final response = await http.get(uri).timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) throw Exception('Location search is temporarily unavailable.');
      final values = (jsonDecode(response.body) as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
      if (mounted && locationController.text.trim() == query) setState(() => locationSuggestions = values);
    } catch (exception) {
      if (mounted) setState(() { locationSuggestions = []; error = '$exception'.replaceFirst('Exception: ', ''); });
    } finally {
      if (mounted) setState(() => searchingLocation = false);
    }
  }

  Future<void> selectLocation(Map<String, dynamic> suggestion) async {
    final placeId = '${suggestion['place_id'] ?? ''}';
    final label = '${suggestion['text'] ?? ''}';
    if (placeId.isEmpty) return;
    setState(() { locating = true; locationSuggestions = []; error = null; });
    try {
      final uri = Uri.parse('${GaonApi.baseUrl}/location/place/${Uri.encodeComponent(placeId)}').replace(queryParameters: {'session_token': locationSessionToken});
      final response = await http.get(uri).timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) throw Exception('Could not resolve this location.');
      final place = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
      final latitude = (place['latitude'] as num?)?.toDouble();
      final longitude = (place['longitude'] as num?)?.toDouble();
      if (latitude == null || longitude == null) throw Exception('This location has no usable coordinates.');
      final result = await ResilientApi.nearbyStores(latitude, longitude);
      if (!mounted) return;
      setState(() {
        stores = result.data;
        selectedVillageId = null;
        selectedLocationLabel = '${place['formatted_address'] ?? label}';
        locationController.text = selectedLocationLabel!;
        usingLocation = true;
        locating = false;
        cached = result.fromCache;
        cachedAt = result.cachedAt;
      });
    } catch (exception) {
      if (mounted) setState(() { locating = false; error = '$exception'.replaceFirst('Exception: ', ''); });
    }
  }

  Future<void> useMyLocation() async {
    setState(() { locating = true; error = null; locationSuggestions = []; });
    try {
      if (!await Geolocator.isLocationServiceEnabled()) throw Exception('Location services are switched off on this device.');
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) throw Exception('Location permission is required to find nearby shops.');
      final position = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high));
      final result = await ResilientApi.nearbyStores(position.latitude, position.longitude);
      if (!mounted) return;
      setState(() {
        stores = result.data;
        selectedVillageId = null;
        selectedLocationLabel = 'Current location';
        locationController.text = 'Current location';
        usingLocation = true;
        locating = false;
        cached = result.fromCache;
        cachedAt = result.cachedAt;
      });
    } catch (exception) {
      if (mounted) setState(() { locating = false; error = '$exception'.replaceFirst('Exception: ', ''); });
    }
  }

  Future<void> logout() async { await GaonApi.logout(); if (mounted) widget.onLoggedOut(); }

  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('GaonOne', style: TextStyle(fontWeight: FontWeight.w900)), actions: [IconButton(onPressed: logout, icon: const Icon(Icons.logout))]),
    body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(
      onRefresh: usingLocation ? useMyLocation : load,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        Text('What’s available around you?', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 6),
        const Text('Search any area, colony, neighbourhood, village, town, city, landmark or pincode.'),
        if (cached) Card(child: ListTile(leading: const Icon(Icons.cloud_off_outlined), title: const Text('Showing saved market data'), subtitle: Text(cachedAt == null ? 'Reconnect and pull to refresh for live availability.' : 'Last synced ${cachedAt!.toLocal()}'), trailing: IconButton(onPressed: load, icon: const Icon(Icons.refresh)))) ,
        const SizedBox(height: 14),
        TextField(
          controller: locationController,
          onChanged: searchLocation,
          decoration: InputDecoration(
            labelText: 'Search location',
            hintText: 'Area, colony, city, village, landmark or pincode',
            prefixIcon: const Icon(Icons.location_on_outlined),
            suffixIcon: searchingLocation ? const Padding(padding: EdgeInsets.all(14), child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))) : IconButton(onPressed: locating ? null : useMyLocation, icon: const Icon(Icons.my_location)),
          ),
        ),
        if (locationSuggestions.isNotEmpty) Card(child: Column(children: locationSuggestions.map((item) => ListTile(leading: const Icon(Icons.place_outlined), title: Text('${item['text'] ?? ''}'), onTap: () => selectLocation(item))).toList())),
        const SizedBox(height: 12),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Browse active service villages'),
          subtitle: const Text('Optional fallback'),
          children: [DropdownButtonFormField<String>(
            initialValue: selectedVillageId,
            decoration: const InputDecoration(labelText: 'Select service village'),
            items: villages.map((v) => DropdownMenuItem(value: v.id, child: Text('${v.name}, ${v.district}'))).toList(),
            onChanged: (value) { setState(() { selectedVillageId = value; selectedLocationLabel = null; locationController.clear(); usingLocation = false; }); load(); },
          )],
        ),
        const SizedBox(height: 18),
        if (usingLocation) Padding(padding: const EdgeInsets.only(bottom: 10), child: Row(children: [const Icon(Icons.location_on_outlined, size: 18), const SizedBox(width: 6), Expanded(child: Text('${stores.length} shops near ${selectedLocationLabel ?? 'this location'}'))])),
        if (error != null) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        ...stores.map((store) => Card(child: ListTile(
          title: Text(store.name, style: const TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(store.landmark ?? store.description ?? 'Local store'), if (store.distanceKm != null) Text('${store.distanceKm!.toStringAsFixed(1)} km away')]),
          trailing: Icon(store.deliveryEnabled ? Icons.delivery_dining : Icons.storefront),
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => StoreScreen(store: store))),
        ))),
        if (stores.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('No stores found here yet. Try another nearby area, landmark or pincode.'))),
      ]),
    ),
  );
}
