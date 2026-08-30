import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

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
  static const _recentLocationsKey = 'market.recent_locations.v1';
  List<Village> villages = [];
  List<StoreModel> stores = [];
  List<Map<String, dynamic>> locationSuggestions = [];
  List<Map<String, dynamic>> recentLocations = [];
  final locationController = TextEditingController();
  Timer? locationDebounce;
  String? selectedVillageId;
  String? selectedLocationLabel;
  String? coverageMessage;
  final String locationSessionToken = '${DateTime.now().microsecondsSinceEpoch}-${Object().hashCode}';
  bool loading = true, locating = false, searchingLocation = false, usingLocation = false, cached = false;
  DateTime? cachedAt;
  String? error;

  @override void initState() { super.initState(); load(); _loadRecents(); }

  @override void dispose() {
    locationDebounce?.cancel();
    locationController.dispose();
    super.dispose();
  }

  Future<void> _loadRecents() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final decoded = jsonDecode(prefs.getString(_recentLocationsKey) ?? '[]') as List;
      if (mounted) setState(() => recentLocations = decoded.map((e) => Map<String, dynamic>.from(e as Map)).take(5).toList());
    } catch (_) {}
  }

  Future<void> _rememberLocation(String label, double latitude, double longitude) async {
    final next = <Map<String, dynamic>>[
      {'label': label, 'latitude': latitude, 'longitude': longitude},
      ...recentLocations.where((item) {
        final lat = (item['latitude'] as num?)?.toDouble();
        final lng = (item['longitude'] as num?)?.toDouble();
        return lat == null || lng == null || (lat - latitude).abs() > 0.00001 || (lng - longitude).abs() > 0.00001;
      }),
    ].take(5).toList();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_recentLocationsKey, jsonEncode(next));
    if (mounted) setState(() => recentLocations = next);
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
      final uri = Uri.parse('${GaonApi.baseUrl}/location/autocomplete').replace(queryParameters: {'q': query, 'session_token': locationSessionToken});
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

  Future<String?> _coverage(double latitude, double longitude) async {
    try {
      final uri = Uri.parse('${GaonApi.baseUrl}/location/serviceability').replace(queryParameters: {'latitude': '$latitude', 'longitude': '$longitude'});
      final response = await http.get(uri).timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) return null;
      final value = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
      final serviceable = value['serviceable'] == true;
      final area = value['service_area_name'];
      if (serviceable) return area == null ? 'Delivery is available at this location.' : 'Delivery available through $area.';
      return area == null ? 'GaonOne is not fully live at this exact point yet.' : 'Not fully live here yet. Nearest active service area: $area.';
    } catch (_) { return null; }
  }

  Future<void> _showLocation(String label, double latitude, double longitude) async {
    final result = await ResilientApi.nearbyStores(latitude, longitude);
    final coverage = await _coverage(latitude, longitude);
    await _rememberLocation(label, latitude, longitude);
    if (!mounted) return;
    setState(() {
      stores = result.data;
      selectedVillageId = null;
      selectedLocationLabel = label;
      locationController.text = label;
      locationSuggestions = [];
      usingLocation = true;
      locating = false;
      cached = result.fromCache;
      cachedAt = result.cachedAt;
      coverageMessage = coverage;
    });
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
      await _showLocation('${place['formatted_address'] ?? label}', latitude, longitude);
    } catch (exception) {
      if (mounted) setState(() { locating = false; error = '$exception'.replaceFirst('Exception: ', ''); });
    }
  }

  Future<void> useRecent(Map<String, dynamic> item) async {
    final latitude = (item['latitude'] as num?)?.toDouble();
    final longitude = (item['longitude'] as num?)?.toDouble();
    final label = '${item['label'] ?? 'Recent location'}';
    if (latitude == null || longitude == null) return;
    setState(() { locating = true; error = null; });
    try { await _showLocation(label, latitude, longitude); } catch (exception) { if (mounted) setState(() { locating = false; error = '$exception'.replaceFirst('Exception: ', ''); }); }
  }

  Future<void> useMyLocation() async {
    setState(() { locating = true; error = null; locationSuggestions = []; });
    try {
      if (!await Geolocator.isLocationServiceEnabled()) throw Exception('Location services are switched off on this device.');
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) throw Exception('Location permission is required to find nearby shops.');
      final position = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high));
      var label = 'Current location';
      try {
        final uri = Uri.parse('${GaonApi.baseUrl}/location/reverse').replace(queryParameters: {'latitude': '${position.latitude}', 'longitude': '${position.longitude}', 'session_token': locationSessionToken});
        final response = await http.get(uri).timeout(const Duration(seconds: 8));
        if (response.statusCode >= 200 && response.statusCode < 300 && response.body != 'null') {
          final place = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
          label = '${place['formatted_address'] ?? label}';
        }
      } catch (_) {}
      await _showLocation(label, position.latitude, position.longitude);
    } catch (exception) {
      if (mounted) setState(() { locating = false; error = '$exception'.replaceFirst('Exception: ', ''); });
    }
  }

  Future<void> logout() async { await GaonApi.logout(); if (mounted) widget.onLoggedOut(); }

  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('GaonOne', style: TextStyle(fontWeight: FontWeight.w900)), actions: [IconButton(onPressed: logout, icon: const Icon(Icons.logout))]),
    body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(
      onRefresh: usingLocation ? () async { if (recentLocations.isNotEmpty) await useRecent(recentLocations.first); } : load,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        Text('What’s available around you?', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 6),
        const Text('Search any area, colony, neighbourhood, village, town, city, landmark or pincode.'),
        if (cached) Card(child: ListTile(leading: const Icon(Icons.cloud_off_outlined), title: const Text('Showing saved market data'), subtitle: Text(cachedAt == null ? 'Reconnect and pull to refresh for live availability.' : 'Last synced ${cachedAt!.toLocal()}'), trailing: IconButton(onPressed: load, icon: const Icon(Icons.refresh)))) ,
        if (coverageMessage != null) Card(child: ListTile(leading: const Icon(Icons.public), title: Text(coverageMessage!))),
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
        if (locationController.text.trim().length < 2 && recentLocations.isNotEmpty) Card(child: Column(children: [const ListTile(dense: true, title: Text('Recent locations', style: TextStyle(fontWeight: FontWeight.w700))), ...recentLocations.map((item) => ListTile(leading: const Icon(Icons.history), title: Text('${item['label'] ?? 'Recent location'}'), onTap: () => useRecent(item)))])),
        const SizedBox(height: 12),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Browse active service villages'),
          subtitle: const Text('Optional fallback'),
          children: [DropdownButtonFormField<String>(
            initialValue: selectedVillageId,
            decoration: const InputDecoration(labelText: 'Select service village'),
            items: villages.map((v) => DropdownMenuItem(value: v.id, child: Text('${v.name}, ${v.district}'))).toList(),
            onChanged: (value) { setState(() { selectedVillageId = value; selectedLocationLabel = null; locationSuggestions = []; coverageMessage = null; locationController.clear(); usingLocation = false; }); load(); },
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
