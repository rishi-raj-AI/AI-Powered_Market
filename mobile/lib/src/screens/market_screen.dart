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
  String? selected;
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final v = await GaonApi.villages();
      final s = await GaonApi.stores(selected);
      if (mounted) setState(() { villages = v; stores = s; loading = false; error = null; });
    } catch (e) {
      if (mounted) setState(() { loading = false; error = e.toString(); });
    }
  }

  Future<void> logout() async {
    await GaonApi.logout();
    widget.onLoggedOut();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('GaonOne', style: TextStyle(fontWeight: FontWeight.w900)),
      actions: [IconButton(onPressed: logout, icon: const Icon(Icons.logout))],
    ),
    body: loading
        ? const Center(child: CircularProgressIndicator())
        : RefreshIndicator(
            onRefresh: load,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Nearby market', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: selected,
                  decoration: const InputDecoration(labelText: 'Village', border: OutlineInputBorder()),
                  items: villages.map((v) => DropdownMenuItem(value: v.id, child: Text('${v.name}, ${v.district}'))).toList(),
                  onChanged: (x) { setState(() => selected = x); load(); },
                ),
                const SizedBox(height: 18),
                if (error != null) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(error!, style: const TextStyle(color: Colors.red))),
                ...stores.map((s) => Card(
                  child: ListTile(
                    title: Text(s.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Text(s.landmark ?? s.description ?? 'Local store'),
                    trailing: Icon(s.deliveryEnabled ? Icons.delivery_dining : Icons.storefront),
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => StoreScreen(store: s))),
                  ),
                )),
                if (stores.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('No stores found in this village yet.'))),
              ],
            ),
          ),
  );
}
