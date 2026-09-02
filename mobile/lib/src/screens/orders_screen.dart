import 'package:flutter/material.dart';
import '../api/gaon_api.dart';
import '../models/models.dart';
import '../widgets/customer_live_tracking.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});
  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  List<OrderModel> orders = [];
  bool loading = true;
  String? error;
  String? payingOrderId;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await GaonApi.orders();
      if (mounted) setState(() { orders = data; loading = false; error = null; });
    } catch (e) {
      if (mounted) setState(() { loading = false; error = '$e'; });
    }
  }

  Future<void> pay(OrderModel order) async {
    setState(() => payingOrderId = order.id);
    try {
      final paid = await GaonApi.openRazorpayCheckout(order);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(paid ? 'Payment confirmed.' : 'Payment was not completed.')));
      await load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => payingOrderId = null);
    }
  }

  Future<void> cancel(OrderModel order) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancel order?'),
        content: Text('${order.orderNumber} can only be cancelled before the store accepts it.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Keep order')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Cancel order')),
        ],
      ),
    );
    if (yes == true) {
      try { await GaonApi.cancelOrder(order.id); await load(); }
      catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
    }
  }

  Future<void> detail(OrderModel order) async {
    try {
      final detail = await GaonApi.orderDetail(order.id);
      if (!mounted) return;
      final items = detail['items'] as List? ?? [];
      showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        builder: (sheetContext) => SafeArea(
          child: SingleChildScrollView(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: 20 + MediaQuery.of(sheetContext).viewInsets.bottom,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(order.orderNumber, style: Theme.of(sheetContext).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                Text('${detail['store_name'] ?? 'Store'} • ${order.status.replaceAll('_', ' ')}'),
                const Divider(),
                ...items.map((item) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${item['product_name'] ?? 'Item'}'),
                  subtitle: Text('${item['quantity']} × ₹${item['unit_price']}'),
                  trailing: Text('₹${item['line_total']}'),
                )),
                const Divider(),
                Text('Deliver to: ${detail['house_details'] ?? ''} ${detail['customer_landmark'] ?? ''}'),
                if (detail['customer_directions'] != null) Text('Directions: ${detail['customer_directions']}'),
                if (order.status == 'out_for_delivery' || order.status == 'delivered') ...[
                  const SizedBox(height: 12),
                  CustomerLiveTracking(orderId: order.id),
                ],
                if (order.status == 'delivered') OutlinedButton.icon(onPressed: () => reorder(order, sheetContext), icon: const Icon(Icons.replay), label: const Text('Preview reorder')),
                const SizedBox(height: 10),
                Align(alignment: Alignment.centerRight, child: Text('Total ₹${order.total}', style: const TextStyle(fontWeight: FontWeight.w800))),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  Future<void> reorder(OrderModel order, BuildContext sheetContext) async {
    try {
      final preview = await GaonApi.reorderPreview(order.id);
      if (!sheetContext.mounted) return;
      final items = (preview['items'] as List? ?? []).cast<Map<String, dynamic>>();
      final add = await showDialog<bool>(context: sheetContext, builder: (dialogContext) => AlertDialog(title: const Text('Buy this basket again?'), content: Text('${preview['available_items']} available • ${preview['unavailable_items']} unavailable\nEstimated subtotal ₹${preview['estimated_subtotal']}\n\nCurrent stock and prices are shown; checkout verifies them again.'), actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Not now')),FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Add available'))]));
      if (add == true) {
        for (final item in items) { if (item['available'] == true && item['listing_id'] != null && (item['available_quantity'] as num) > 0) await GaonApi.addToCart('${item['listing_id']}', quantity: (item['available_quantity'] as num).toInt()); }
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Available items added. Checkout will verify them again.')));
      }
    } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('My orders', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
          const Text('Track fulfilment, review delivery details and manage eligible cancellations.'),
          if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          if (orders.isEmpty) const Padding(padding: EdgeInsets.all(40), child: Center(child: Text('No orders yet.'))),
          ...orders.map((order) => Card(
            child: InkWell(
              onTap: () => detail(order),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [Expanded(child: Text(order.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))), Chip(label: Text(order.status.replaceAll('_', ' ')))]),
                    Text('₹${order.total} • ${order.paymentMethod.toUpperCase()} • ${_paymentLabel(order.paymentStatus)}'),
                    const SizedBox(height: 8),
                    Wrap(spacing: 8, children: [
                      OutlinedButton.icon(onPressed: () => detail(order), icon: const Icon(Icons.receipt_long), label: const Text('Details')),
                      if (order.status == 'placed') TextButton(onPressed: () => cancel(order), child: const Text('Cancel order')),
                      if (order.paymentMethod == 'upi' && order.paymentStatus == 'pending' && order.status != 'cancelled' && order.status != 'returned')
                        FilledButton.icon(
                          onPressed: payingOrderId == order.id ? null : () => pay(order),
                          icon: const Icon(Icons.payments_outlined),
                          label: Text(payingOrderId == order.id ? 'Opening…' : 'Pay now'),
                        ),
                    ]),
                  ],
                ),
              ),
            ),
          )),
        ],
      ),
    );
  }
}


/// Payment wording that matches what the backend actually knows.
///
/// `refund_pending` means the money is owed and on its way back; only
/// `refunded` means a provider confirmed it landed.
String _paymentLabel(String status) => switch (status) {
      'refund_pending' => 'refund in progress',
      'refunded' => 'refunded',
      _ => status,
    };
