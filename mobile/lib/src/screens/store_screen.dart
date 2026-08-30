import 'package:flutter/material.dart';

import '../api/commerce_intelligence_api.dart';
import '../api/gaon_api.dart';
import '../api/resilient_api.dart';
import '../models/models.dart';
import '../widgets/fulfillment_recommendation_card.dart';

class StoreScreen extends StatefulWidget {
  final StoreModel store;
  const StoreScreen({super.key, required this.store});
  @override State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  List<StoreProduct> products = [];
  Map<String, dynamic>? preparation;
  bool loading = true, cached = false;
  DateTime? cachedAt;
  String? error;
  String? preparationError;
  String query = '';
  final Set<String> adding = {};

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result = await ResilientApi.storeProducts(widget.store.id);
      Map<String, dynamic>? nextPreparation;
      String? nextPreparationError;
      try {
        nextPreparation = await CommerceIntelligenceApi.preparationEstimate(
          widget.store.id,
        );
      } catch (exception) {
        nextPreparationError = '$exception'.replaceFirst('Exception: ', '');
      }
      if (!mounted) return;
      setState(() {
        products = result.data;
        cached = result.fromCache;
        cachedAt = result.cachedAt;
        preparation = nextPreparation;
        preparationError = nextPreparationError;
        loading = false;
        error = null;
      });
    } catch (exception) {
      if (mounted) {
        setState(() {
          loading = false;
          error = '$exception'.replaceFirst('Exception: ', '');
        });
      }
    }
  }

  Future<bool> _prepareCartForStore() async {
    final cart = await GaonApi.cart();
    if (cart.items.isEmpty ||
        cart.storeId == null ||
        cart.storeId == widget.store.id) {
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
    if (cached) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Reconnect before changing the cart so stock can be verified.',
          ),
        ),
      );
      return;
    }
    if (adding.contains(product.id)) return;
    setState(() => adding.add(product.id));
    try {
      if (!await _prepareCartForStore()) return;
      await GaonApi.addToCart(product.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${product.name} added to cart')),
        );
      }
    } catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('$exception'.replaceFirst('Exception: ', '')),
          ),
        );
      }
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
              (p) =>
                  p.name.toLowerCase().contains(normalized) ||
                  p.unit.toLowerCase().contains(normalized),
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
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    widget.store.landmark ??
                        widget.store.description ??
                        'Local store',
                  ),
                  if (preparation != null)
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.schedule_outlined),
                        title: Text(
                          CommerceIntelligenceApi.preparationCopy(preparation!),
                        ),
                        subtitle: Text(
                          '${CommerceIntelligenceApi.preparationDetail(preparation!)} Preparation time is an estimate, not a delivery ETA.',
                        ),
                      ),
                    ),
                  if (preparationError != null)
                    const Card(
                      child: ListTile(
                        leading: Icon(Icons.schedule_outlined),
                        title: Text('Preparation estimate unavailable'),
                        subtitle: Text(
                          'You can still browse and order. Pull to refresh when the network improves.',
                        ),
                      ),
                    ),
                  FulfillmentRecommendationCard(storeId: widget.store.id),
                  if (cached)
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.cloud_off_outlined),
                        title: const Text('Saved catalogue'),
                        subtitle: Text(
                          cachedAt == null
                              ? 'Prices and stock may have changed.'
                              : 'Last synced ${cachedAt!.toLocal()}. Cart changes are paused until reconnect.',
                        ),
                      ),
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
                        child: Text(
                          error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    ),
                  if (visibleProducts.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(32),
                      child: Center(
                        child: Text(
                          'No matching products available right now.',
                        ),
                      ),
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
                                  Text(
                                    product.name,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    '${product.unit} • ${product.stock} in stock',
                                  ),
                                  if (product.mrp != null &&
                                      product.mrp != product.price)
                                    Text(
                                      'MRP ₹${product.mrp}',
                                      style:
                                          Theme.of(context).textTheme.bodySmall,
                                    ),
                                ],
                              ),
                            ),
                            FilledButton(
                              onPressed: cached ||
                                      product.stock <= 0 ||
                                      adding.contains(product.id)
                                  ? null
                                  : () => addToCart(product),
                              child: adding.contains(product.id)
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
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
