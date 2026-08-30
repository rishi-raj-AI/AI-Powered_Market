import 'package:flutter/material.dart';

import '../api/commerce_intelligence_api.dart';
import '../api/gaon_api.dart';

class BasketRecommendationsCard extends StatefulWidget {
  const BasketRecommendationsCard({super.key});
  @override
  State<BasketRecommendationsCard> createState() => _BasketRecommendationsCardState();
}

class _BasketRecommendationsCardState extends State<BasketRecommendationsCard> {
  List<Map<String, dynamic>> items = [];
  bool loading = true;
  String? error;
  String? busy;

  @override
  void initState() { super.initState(); load(); }

  Future<void> load() async {
    try {
      final next = await CommerceIntelligenceApi.basketRecommendations();
      if (mounted) setState(() { items = next.take(4).toList(); loading = false; error = null; });
    } catch (e) {
      if (mounted) setState(() { loading = false; error = e.toString().replaceFirst('Exception: ', ''); });
    }
  }

  Future<void> add(Map<String, dynamic> item) async {
    final id = item['listing_id'] as String;
    setState(() => busy = id);
    try {
      await GaonApi.addToCart(id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${item['name']} added to cart')));
      await load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))));
    } finally {
      if (mounted) setState(() => busy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Card(child: ListTile(leading: CircularProgressIndicator(), title: Text('Checking useful add-ons…')));
    if (items.isEmpty && error == null) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [Icon(Icons.auto_awesome_outlined), SizedBox(width: 8), Text('Useful add-ons from this store', style: TextStyle(fontWeight: FontWeight.w700))]),
          const SizedBox(height: 4),
          Text('Suggestions use your current basket and live inventory.', style: Theme.of(context).textTheme.bodySmall),
          if (error != null) ...[const SizedBox(height: 8), Text(error!), TextButton(onPressed: load, child: const Text('Retry'))],
          ...items.map((item) => ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(item['name'] as String? ?? 'Item'),
            subtitle: Text('${item['unit'] ?? ''} • ₹${item['price']} • ${(item['reason'] ?? '').toString().replaceAll('_', ' ')}'),
            trailing: OutlinedButton(
              onPressed: busy == item['listing_id'] || ((item['stock_quantity'] as num?) ?? 0) < 1 ? null : () => add(item),
              child: Text(busy == item['listing_id'] ? 'Adding…' : 'Add'),
            ),
          )),
        ]),
      ),
    );
  }
}
