import 'dart:async';
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
  String searchQuery = '';
  double? searchLatitude;
  double? searchLongitude;
  Timer? searchDebounce;
  int searchGeneration = 0;
  bool searchingProducts = false;
  bool hasSearchedProducts = false;
  String? searchError;
  List<Map<String, dynamic>> matchedProducts = [];
  List<Map<String, dynamic>> matchedStores = [];
  String selectedCategory = 'All';
  bool loading = true;
  bool locating = false;
  bool usingLocation = false;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    searchDebounce?.cancel();
    super.dispose();
  }

  void updateSearch(String value) {
    searchDebounce?.cancel();
    final generation = ++searchGeneration;
    setState(() { searchQuery = value; searchError = null; matchedProducts = []; matchedStores = []; searchingProducts = false; hasSearchedProducts = false; });
    if (value.trim().isEmpty || searchLatitude == null || searchLongitude == null) return;
    searchDebounce = Timer(const Duration(milliseconds: 350), () async {
      if (!mounted || generation != searchGeneration) return;
      setState(() => searchingProducts = true);
      try {
        final result = await GaonApi.discoverySearch(value.trim(), latitude: searchLatitude!, longitude: searchLongitude!);
        if (!mounted || generation != searchGeneration) return;
        setState(() {
          matchedProducts = (result['products'] as List? ?? []).map((item) => Map<String, dynamic>.from(item as Map)).toList();
          matchedStores = (result['stores'] as List? ?? []).map((item) => Map<String, dynamic>.from(item as Map)).toList();
          searchingProducts = false;
          hasSearchedProducts = true;
        });
      } catch (exception) {
        if (!mounted || generation != searchGeneration) return;
        setState(() { searchingProducts = false; searchError = exception.toString(); });
      }
    });
  }

  Future<void> load() async {
    try {
      final loadedVillages = await GaonApi.villages();
      final loadedStores = await GaonApi.stores(selectedVillageId);
      if (!mounted) return;
      searchDebounce?.cancel();
      ++searchGeneration;
      setState(() {
        searchLatitude = null;
        searchLongitude = null;
        matchedProducts = [];
        matchedStores = [];
        hasSearchedProducts = false;
        searchingProducts = false;
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
      searchDebounce?.cancel();
      ++searchGeneration;
      setState(() {
        matchedProducts = [];
        matchedStores = [];
        hasSearchedProducts = false;
        searchingProducts = false;
        stores = nearby;
        searchLatitude = position.latitude;
        searchLongitude = position.longitude;
        selectedVillageId = null;
        usingLocation = true;
        locating = false;
      });
      if (searchQuery.trim().isNotEmpty) updateSearch(searchQuery);
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

  static const categories = <(String, IconData)>[
    ('All', Icons.apps_rounded),
    ('Food', Icons.restaurant_rounded),
    ('Groceries', Icons.shopping_basket_rounded),
    ('Vegetables', Icons.eco_rounded),
    ('Agriculture', Icons.agriculture_rounded),
    ('Hardware', Icons.handyman_rounded),
    ('Retail', Icons.storefront_rounded),
  ];

  @override
  Widget build(BuildContext context) {
    final query = searchQuery.trim().toLowerCase();
    final filtered = stores.where((store) {
      final text = '${store.name} ${store.description ?? ''} ${store.landmark ?? ''}'.toLowerCase();
      final matchesQuery = query.isEmpty || text.contains(query);
      final matchesCategory = selectedCategory == 'All' ||
          text.contains(selectedCategory.toLowerCase()) ||
          (selectedCategory == 'Vegetables' && (text.contains('fruit') || text.contains('sabzi'))) ||
          (selectedCategory == 'Groceries' && (text.contains('kirana') || text.contains('grocery')));
      return matchesQuery && matchesCategory;
    }).toList();

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
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
                children: [
                  Container(
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [Color(0xFF145B33), Color(0xFF29985B)]),
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('YOUR NEIGHBOURHOOD, DELIVERED', style: TextStyle(color: Color(0xFFBDE8C8), fontWeight: FontWeight.w700, fontSize: 11, letterSpacing: 1)),
                      const SizedBox(height: 10),
                      const Text('Everything local.\\nOne happy place.', style: TextStyle(color: Colors.white, fontSize: 29, fontWeight: FontWeight.w900, height: 1.15)),
                      const SizedBox(height: 10),
                      const Text('Food, fresh essentials and trusted nearby shops.', style: TextStyle(color: Colors.white70)),
                    ]),
                  ),
                  const SizedBox(height: 18),
                  TextField(
                    onChanged: updateSearch,
                    decoration: InputDecoration(
                      hintText: 'Search nearby stores or essentials',
                      prefixIcon: const Icon(Icons.search_rounded),
                      suffixIcon: searchQuery.isEmpty ? null : IconButton(
                        tooltip: 'Clear search',
                        onPressed: () => updateSearch(''),
                        icon: const Icon(Icons.close_rounded),
                      ),
                      filled: true,
                      fillColor: Colors.white,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: BorderSide.none),
                    ),
                  ),
                  if (searchQuery.trim().isNotEmpty && searchLatitude == null)
                    const Padding(padding: EdgeInsets.only(top: 10), child: Text('Select “Use my current location” to search products across nearby stores. Store names can be filtered without GPS.')),
                  if (searchingProducts) const Padding(padding: EdgeInsets.only(top: 10), child: LinearProgressIndicator()),
                  if (searchError != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(searchError!, style: const TextStyle(color: Color(0xFFB42318)))),
                  if (searchQuery.trim().isNotEmpty && searchLatitude != null && hasSearchedProducts && !searchingProducts && searchError == null) ...[
                    const SizedBox(height: 16),
                    Text('Matching products', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                    if (matchedProducts.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Text('No nearby products match this search.')),
                    ...matchedProducts.map((product) => Card(child: ListTile(
                      leading: const Icon(Icons.shopping_basket_rounded, color: Color(0xFF1F7A45)),
                      title: Text('${product['name']}'),
                      subtitle: Text('${product['store_name']} · ${product['unit']}'),
                      trailing: Text('₹${product['price']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                      onTap: () async {
                        final store = stores.where((item) => item.id == product['store_id']).firstOrNull;
                        if (store != null) await Navigator.push(context, MaterialPageRoute(builder: (_) => StoreScreen(store: store)));
                      },
                    ))),
                  ],
                  const SizedBox(height: 18),
                  Text('Explore categories', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 92,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: categories.length,
                      separatorBuilder: (_, __) => const SizedBox(width: 10),
                      itemBuilder: (context, index) {
                        final (label, icon) = categories[index];
                        final selected = selectedCategory == label;
                        return InkWell(
                          borderRadius: BorderRadius.circular(18),
                          onTap: () => setState(() => selectedCategory = label),
                          child: Container(
                            width: 88,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            decoration: BoxDecoration(
                              color: selected ? const Color(0xFFE0F2E5) : Colors.white,
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(color: selected ? const Color(0xFF1F7A45) : const Color(0xFFE8ECE7)),
                            ),
                            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                              Icon(icon, color: const Color(0xFF1F7A45), size: 28),
                              const SizedBox(height: 7),
                              Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                            ]),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 22),
                  Text('Find shops near you', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 8),
                  FilledButton.tonalIcon(
                    onPressed: locating ? null : useMyLocation,
                    icon: locating ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.my_location),
                    label: Text(locating ? 'Finding nearby shops…' : 'Use my current location'),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    initialValue: selectedVillageId,
                    decoration: const InputDecoration(labelText: 'Or choose area / locality'),
                    items: villages.map((v) => DropdownMenuItem(value: v.id, child: Text('${v.name}, ${v.district}'))).toList(),
                    onChanged: (value) {
                      searchDebounce?.cancel();
                      searchGeneration++;
                      setState(() { selectedVillageId = value; usingLocation = false; searchLatitude = null; searchLongitude = null; matchedProducts = []; matchedStores = []; searchingProducts = false; });
                      load();
                    },
                  ),
                  const SizedBox(height: 22),
                  Row(children: [
                    Expanded(child: Text('Discover local stores', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))),
                    Text('${filtered.length} found', style: const TextStyle(color: Color(0xFF667069))),
                  ]),
                  const SizedBox(height: 12),
                  if (error != null)
                    Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                  ...filtered.map((store) => Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => StoreScreen(store: store))),
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Row(children: [
                          Container(
                            width: 74, height: 78,
                            decoration: BoxDecoration(color: const Color(0xFFEAF4ED), borderRadius: BorderRadius.circular(16)),
                            child: Icon(store.deliveryEnabled ? Icons.delivery_dining_rounded : Icons.storefront_rounded, size: 35, color: const Color(0xFF1F7A45)),
                          ),
                          const SizedBox(width: 14),
                          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(store.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
                            const SizedBox(height: 5),
                            Text(store.landmark ?? store.description ?? 'Your neighbourhood store', maxLines: 2, overflow: TextOverflow.ellipsis),
                            const SizedBox(height: 6),
                            Text('${store.isOpenNow ? '● Open now' : '● Closed now'}${store.distanceKm == null ? '' : '  ·  ${store.distanceKm!.toStringAsFixed(1)} km'}', style: TextStyle(fontWeight: FontWeight.w700, color: store.isOpenNow ? const Color(0xFF1F7A45) : const Color(0xFFB42318))),
                          ])),
                          const Icon(Icons.chevron_right_rounded),
                        ]),
                      ),
                    ),
                  )),
                  if (filtered.isEmpty)
                    const Padding(padding: EdgeInsets.all(28), child: Center(child: Text('No matching stores here yet. Try another search, category or locality.', textAlign: TextAlign.center))),
                ],
              ),
            ),
    );
  }
}
