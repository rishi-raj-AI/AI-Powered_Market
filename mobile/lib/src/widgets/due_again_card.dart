import 'package:flutter/material.dart';

import '../api/commerce_intelligence_api.dart';
import '../api/gaon_api.dart';

class DueAgainCard extends StatefulWidget {
  const DueAgainCard({super.key});

  @override
  State<DueAgainCard> createState() => _DueAgainCardState();
}

class _DueAgainCardState extends State<DueAgainCard> {
  List<Map<String, dynamic>> items = [];
  bool loading = true;
  String? error;
  String? message;
  String? busyProduct;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final next = await CommerceIntelligenceApi.repeatPurchaseCadence();
      if (!mounted) return;
      setState(() {
        items = next
            .where(
              (item) =>
                  item['due'] == true ||
                  ((item['urgency_score'] as num?) ?? 0) >= 0.65,
            )
            .take(6)
            .toList();
      });
    } catch (exception) {
      if (mounted) {
        setState(() {
          error = '$exception'.replaceFirst('Exception: ', '');
        });
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> buyAgain(Map<String, dynamic> item) async {
    final listingId = item['listing_id'] as String?;
    if (listingId == null) return;
    final productId = item['product_id'] as String? ?? listingId;
    setState(() {
      busyProduct = productId;
      message = null;
    });
    try {
      await GaonApi.addToCart(listingId);
      if (mounted) {
        setState(() {
          message = '${item['product_name']} added after a live stock check.';
        });
      }
    } catch (exception) {
      if (mounted) {
        setState(() {
          message = '$exception'.replaceFirst('Exception: ', '');
        });
      }
    } finally {
      if (mounted) setState(() => busyProduct = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Card(
        child: ListTile(
          leading: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          title: Text('Checking what may be due again…'),
        ),
      );
    }
    if (error != null) {
      return Card(
        child: ListTile(
          leading: const Icon(Icons.history),
          title: const Text('Repeat suggestions unavailable'),
          subtitle: Text(error!),
          trailing: IconButton(
            tooltip: 'Retry',
            onPressed: load,
            icon: const Icon(Icons.refresh),
          ),
        ),
      );
    }
    if (items.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Due again',
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
            ),
            const SizedBox(height: 4),
            const Text(
              'Based only on your delivered-order history. Live stock is checked before adding anything.',
            ),
            if (message != null) ...[
              const SizedBox(height: 8),
              Text(message!, style: Theme.of(context).textTheme.bodySmall),
            ],
            const SizedBox(height: 8),
            ...items.map((item) {
              final productId = item['product_id'] as String? ?? '';
              final canBuy =
                  item['available_now'] == true && item['listing_id'] != null;
              return ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(item['product_name'] as String? ?? 'Repeat item'),
                subtitle: Text(
                  '${CommerceIntelligenceApi.cadenceCopy(item)} • bought ${item['purchase_count'] ?? 0} times',
                ),
                trailing: canBuy
                    ? FilledButton.icon(
                        onPressed: busyProduct == productId
                            ? null
                            : () => buyAgain(item),
                        icon: busyProduct == productId
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.add_shopping_cart, size: 17),
                        label: const Text('Buy again'),
                      )
                    : const Text('Check store'),
              );
            }),
          ],
        ),
      ),
    );
  }
}
