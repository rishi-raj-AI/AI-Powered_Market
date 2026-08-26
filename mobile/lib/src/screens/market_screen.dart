import 'package:flutter/material.dart';

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

  Future<void> logout() async {
    await GaonApi.logout();
    if (!mounted) return;
    widget.onLoggedOut();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'GaonOne',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        actions: [
          IconButton(onPressed: logout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    'Nearby market',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selectedVillageId,
                    decoration: const InputDecoration(
                      labelText: 'Village',
                      border: OutlineInputBorder(),
                    ),
                    items: villages
                        .map(
                          (village) => DropdownMenuItem(
                            value: village.id,
                            child: Text('${village.name}, ${village.district}'),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      setState(() => selectedVillageId = value);
                      load();
                    },
                  ),
                  const SizedBox(height: 18),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        error!,
                        style: const TextStyle(color: Colors.red),
                      ),
                    ),
                  ...stores.map(
                    (store) => Card(
                      child: ListTile(
                        title: Text(
                          store.name,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        subtitle: Text(
                          store.landmark ?? store.description ?? 'Local store',
                        ),
                        trailing: Icon(
                          store.deliveryEnabled
                              ? Icons.delivery_dining
                              : Icons.storefront,
                        ),
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => StoreScreen(store: store),
                          ),
                        ),
                      ),
                    ),
                  ),
                  if (stores.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(
                        child: Text('No stores found in this village yet.'),
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}
