import 'package:flutter/material.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

class StoreScreen extends StatefulWidget {
  final StoreModel store;

  const StoreScreen({super.key, required this.store});

  @override
  State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  List<StoreProduct> products = [];
  bool loading = true;
  String? error;
  String query = '';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result = await GaonApi.storeProducts(widget.store.id);
      if (!mounted) return;
      setState(() {
        products = result;
        loading = false;
        error = null;
      });
      // Images are optional: a slow or unavailable media service must not
      // prevent shopping, especially on unreliable mobile connections.
      try {
        final images = await GaonApi.approvedStoreImageUrls(widget.store.id);
        if (mounted) setState(() => approvedImages = images);
      } catch (_) {
        if (mounted) setState(() => approvedImages = {});
      }
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = exception.toString();
      });
    }
  }

  Future<void> addToCart(StoreProduct product) async {
    try {
      await GaonApi.addToCart(product.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${product.name} added to cart')),
      );
    } catch (exception) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(exception.toString())),
      );
    }
  }

  Future<void> alternatives(StoreProduct product) async {
    try {
      final items = await GaonApi.substitutions(product.id);
      if (!mounted) return;
      await showModalBottomSheet<void>(context: context, builder: (sheetContext) => SafeArea(child: Padding(padding: const EdgeInsets.all(20), child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Choose a replacement manually', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        const Text('Nothing is substituted automatically. Checkout revalidates your choice.'),
        if (items.isEmpty) const Padding(padding: EdgeInsets.only(top: 12), child: Text('No same-store alternative is available.')),
        ...items.take(3).map((item) => ListTile(contentPadding: EdgeInsets.zero, title: Text('${item['name']}'), subtitle: Text('${item['unit']} • ₹${item['price']}'), trailing: FilledButton(onPressed: () async { await GaonApi.addToCart('${item['listing_id']}'); if (sheetContext.mounted) Navigator.pop(sheetContext); }, child: const Text('Choose')))),
      ]))));
    } catch (exception) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$exception'))); }
  }

  @override
  Widget build(BuildContext context) {
    final visibleProducts = products.where((product) => product.name.toLowerCase().contains(query.trim().toLowerCase())).toList();
    return Scaffold(
      appBar: AppBar(title: Text(widget.store.name)),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Container(
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [Color(0xFF145B33), Color(0xFF288E53)]),
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Icon(Icons.storefront_rounded, size: 38, color: Colors.white),
                      const SizedBox(height: 12),
                      Text(widget.store.name, style: const TextStyle(color: Colors.white, fontSize: 25, fontWeight: FontWeight.w900)),
                      const SizedBox(height: 7),
                      Text(widget.store.landmark ?? widget.store.description ?? 'Your local neighbourhood store', style: const TextStyle(color: Colors.white70)),
                      const SizedBox(height: 12),
                      Text(widget.store.isOpenNow ? '● Open now' : '● Closed now', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                    ]),
                  ),
                  const SizedBox(height: 18),
                  TextField(
                    onChanged: (value) => setState(() => query = value),
                    decoration: InputDecoration(
                      hintText: 'Search products in this store',
                      prefixIcon: const Icon(Icons.search_rounded),
                      filled: true,
                      fillColor: Colors.white,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 22),
                  Row(children: [
                    Expanded(child: Text('Shop products', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))),
                    Text('${visibleProducts.length} items', style: const TextStyle(color: Color(0xFF667069))),
                  ]),
                  const SizedBox(height: 12),
                  if (error != null) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                  ...visibleProducts.map((product) => Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    clipBehavior: Clip.antiAlias,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(children: [
                        Container(
                          width: 80, height: 92,
                          decoration: BoxDecoration(color: const Color(0xFFEAF4ED), borderRadius: BorderRadius.circular(14)),
                          child: approvedImages[product.id] == null
                              ? const Icon(Icons.shopping_basket_rounded, color: Color(0xFF1F7A45), size: 34)
                              : Image.network(
                                  approvedImages[product.id]!,
                                  fit: BoxFit.cover,
                                  width: 80,
                                  height: 92,
                                  errorBuilder: (_, __, ___) => const Icon(Icons.shopping_basket_rounded, color: Color(0xFF1F7A45), size: 34),
                                ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(product.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                          const SizedBox(height: 4),
                          Text('${product.unit} · ${product.stock > 0 ? 'In stock' : 'Out of stock'}', style: TextStyle(color: product.stock > 0 ? const Color(0xFF1F7A45) : const Color(0xFFB42318))),
                          const SizedBox(height: 6),
                          Text('₹${product.price}', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17)),
                        ])),
                        const SizedBox(width: 8),
                        Column(mainAxisSize: MainAxisSize.min, children: [
                          FilledButton.tonal(
                            onPressed: product.stock <= 0 ? null : () => addToCart(product),
                            child: const Text('ADD'),
                          ),
                          if (product.stock <= 5)
                            TextButton(onPressed: () => alternatives(product), child: const Text('Alternatives')),
                        ]),
                      ]),
                    ),
                  )),
                  if (visibleProducts.isEmpty && error == null)
                    const Padding(padding: EdgeInsets.all(28), child: Center(child: Text('No matching products. Try another search.', textAlign: TextAlign.center))),
                ],
              ),
            ),
    );
  }
}
