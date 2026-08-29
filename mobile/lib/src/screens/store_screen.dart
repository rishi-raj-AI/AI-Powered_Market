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
  final Set<String> adding = {};

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
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = exception.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  Future<bool> _prepareCartForStore() async {
    final cart = await GaonApi.cart();
    if (cart.items.isEmpty || cart.storeId == null || cart.storeId == widget.store.id) {
      return true;
    }
    if (!mounted) return false;
    final replace = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Start a new cart?'),
        content: const Text(
          'GaonOne keeps one store per order so delivery and inventory stay reliable. Your current cart is from another store.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Keep current cart'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Clear and continue'),
          ),
        ],
      ),
    );
    if (replace != true) return false;
    await GaonApi.clearCart();
    return true;
  }

  Future<void> addToCart(StoreProduct product) async {
    if (adding.contains(product.id)) return;
    setState(() => adding.add(product.id));
    try {
      if (!await _prepareCartForStore()) return;
      await GaonApi.addToCart(product.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${product.name} added to cart'),
          action: SnackBarAction(label: 'Done', onPressed: () {}),
        ),
      );
    } catch (exception) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(exception.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) setState(() => adding.remove(product.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final normalized = query.trim().toLowerCase();
    final visibleProducts = normalized.isEmpty
        ? products
        : products
            .where(
              (product) =>
                  product.name.toLowerCase().contains(normalized) ||
                  product.unit.toLowerCase().contains(normalized),
            )
            .toList();

    return Scaffold(
      appBar: AppBar(title: Text(widget.store.name)),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    widget.store.name,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  Text(widget.store.landmark ?? widget.store.description ?? 'Local store'),
                  if (widget.store.distanceKm != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text('${widget.store.distanceKm!.toStringAsFixed(1)} km away'),
                    ),
                  const SizedBox(height: 16),
                  TextField(
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search),
                      labelText: 'Search this store',
                      hintText: 'Rice, milk, vegetables…',
                    ),
                    onChanged: (value) => setState(() => query = value),
                  ),
                  const SizedBox(height: 16),
                  if (error != null)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                      ),
                    ),
                  if (visibleProducts.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(32),
                      child: Center(child: Text('No matching products available right now.')),
                    ),
                  ...visibleProducts.map(
                    (product) => Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(product.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                                  const SizedBox(height: 3),
                                  Text('${product.unit} • ${product.stock} in stock'),
                                  if (product.mrp != null && product.mrp != product.price)
                                    Text('MRP ₹${product.mrp}', style: Theme.of(context).textTheme.bodySmall),
                                ],
                              ),
                            ),
                            FilledButton(
                              onPressed: product.stock <= 0 || adding.contains(product.id)
                                  ? null
                                  : () => addToCart(product),
                              child: adding.contains(product.id)
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(strokeWidth: 2),
                                    )
                                  : Text('₹${product.price}  Add'),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
