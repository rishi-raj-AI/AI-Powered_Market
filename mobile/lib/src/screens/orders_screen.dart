import 'package:flutter/material.dart';
import '../api/gaon_api.dart';
import '../api/resilient_api.dart';
import '../models/models.dart';
import '../widgets/customer_live_tracking.dart';

class OrdersScreen extends StatefulWidget { const OrdersScreen({super.key}); @override State<OrdersScreen> createState() => _OrdersScreenState(); }

class _OrdersScreenState extends State<OrdersScreen> {
  List<OrderModel> orders = [];
  bool loading = true, cached = false;
  DateTime? cachedAt;
  String? error, payingOrderId;

  @override void initState() { super.initState(); load(); }

  Future<void> load() async {
    try {
      final result = await ResilientApi.orders();
      if (mounted) setState(() { orders = result.data; cached = result.fromCache; cachedAt = result.cachedAt; loading = false; error = null; });
    } catch (e) { if (mounted) setState(() { loading = false; error = '$e'; }); }
  }

  Future<void> pay(OrderModel order) async {
    if (cached) { _snack('Reconnect before retrying payment.'); return; }
    setState(() => payingOrderId = order.id);
    try { final paid = await GaonApi.openRazorpayCheckout(order); _snack(paid ? 'Payment confirmed.' : 'Payment was not completed.'); await load(); }
    catch (e) { _snack('$e'); }
    finally { if (mounted) setState(() => payingOrderId = null); }
  }

  Future<void> cancel(OrderModel order) async {
    if (cached) { _snack('Reconnect before cancelling so current order state can be verified.'); return; }
    final yes = await showDialog<bool>(context: context, builder: (dialogContext) => AlertDialog(
      title: const Text('Cancel order?'), content: Text('${order.orderNumber} can only be cancelled before the store accepts it.'),
      actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Keep order')), FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Cancel order'))],
    ));
    if (yes == true) { try { await GaonApi.cancelOrder(order.id); await load(); } catch (e) { _snack('$e'); } }
  }

  Future<void> detail(OrderModel order) async {
    if (cached) { _snack('Detailed live tracking needs a connection. Showing saved order summary.'); return; }
    try {
      final detail = await GaonApi.orderDetail(order.id);
      if (!mounted) return;
      final items = detail['items'] as List? ?? [];
      showModalBottomSheet(context: context, isScrollControlled: true, builder: (sheetContext) => SafeArea(child: SingleChildScrollView(
        padding: EdgeInsets.only(left: 20, right: 20, top: 20, bottom: 20 + MediaQuery.of(sheetContext).viewInsets.bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(order.orderNumber, style: Theme.of(sheetContext).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          Text('${detail['store_name'] ?? 'Store'} • ${order.status.replaceAll('_', ' ')}'), const Divider(),
          ...items.map((item) => ListTile(contentPadding: EdgeInsets.zero, title: Text('${item['product_name'] ?? 'Item'}'), subtitle: Text('${item['quantity']} × ₹${item['unit_price']}'), trailing: Text('₹${item['line_total']}'))),
          const Divider(), Text('Deliver to: ${detail['house_details'] ?? ''} ${detail['customer_landmark'] ?? ''}'),
          if (detail['customer_directions'] != null) Text('Directions: ${detail['customer_directions']}'),
          if (order.status == 'out_for_delivery' || order.status == 'delivered') ...[const SizedBox(height: 12), CustomerLiveTracking(orderId: order.id)],
          const SizedBox(height: 10), Align(alignment: Alignment.centerRight, child: Text('Total ₹${order.total}', style: const TextStyle(fontWeight: FontWeight.w800))),
        ]),
      )));
    } catch (e) { _snack('$e'); }
  }

  void _snack(String text) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text.replaceFirst('Exception: ', '')))); }

  @override Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    return RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
      Text('My orders', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      const Text('Track fulfilment, review delivery details and manage eligible cancellations.'),
      if (cached) Card(child: ListTile(leading: const Icon(Icons.cloud_off_outlined), title: const Text('Showing saved order history'), subtitle: Text(cachedAt == null ? 'Reconnect for live status and actions.' : 'Last synced ${cachedAt!.toLocal()}. Actions are paused until reconnect.'))),
      if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      if (orders.isEmpty) const Padding(padding: EdgeInsets.all(40), child: Center(child: Text('No orders yet.'))),
      ...orders.map((order) => Card(child: InkWell(onTap: cached ? null : () => detail(order), child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(order.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))), Chip(label: Text(order.status.replaceAll('_', ' ')))]),
        Text('₹${order.total} • ${order.paymentMethod.toUpperCase()} • ${order.paymentStatus}'), const SizedBox(height: 8),
        Wrap(spacing: 8, children: [
          OutlinedButton.icon(onPressed: cached ? null : () => detail(order), icon: const Icon(Icons.receipt_long), label: const Text('Details')),
          if (order.status == 'placed') TextButton(onPressed: cached ? null : () => cancel(order), child: const Text('Cancel order')),
          if (order.paymentMethod == 'upi' && order.paymentStatus != 'paid' && order.status != 'cancelled') FilledButton.icon(onPressed: cached || payingOrderId == order.id ? null : () => pay(order), icon: const Icon(Icons.payments_outlined), label: Text(payingOrderId == order.id ? 'Opening…' : 'Pay now')),
        ]),
      ]))))),
    ]));
  }
}
