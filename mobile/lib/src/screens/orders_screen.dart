import 'package:flutter/material.dart';
import '../api/gaon_api.dart';
import '../models/models.dart';

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
          child: Padding(
            padding: const EdgeInsets.all(20),
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
                    Text('₹${order.total} • ${order.paymentMethod.toUpperCase()} • ${order.paymentStatus}'),
                    const SizedBox(height: 8),
                    Wrap(spacing: 8, children: [
                      OutlinedButton.icon(onPressed: () => detail(order), icon: const Icon(Icons.receipt_long), label: const Text('Details')),
                      if (order.status == 'placed') TextButton(onPressed: () => cancel(order), child: const Text('Cancel order')),
                      if (order.paymentMethod == 'upi' && order.paymentStatus != 'paid' && order.status != 'cancelled')
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
