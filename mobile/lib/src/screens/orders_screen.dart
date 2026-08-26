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
      if (mounted) {
        setState(() {
          orders = data;
          loading = false;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString();
        });
      }
    }
  }

  Future<void> pay(OrderModel order) async {
    setState(() => payingOrderId = order.id);
    try {
      final paid = await GaonApi.openRazorpayCheckout(order);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(paid ? 'Payment confirmed.' : 'Payment was not completed.')),
      );
      await load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => payingOrderId = null);
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
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (orders.isEmpty)
            const Padding(padding: EdgeInsets.all(40), child: Center(child: Text('No orders yet.'))),
          ...orders.map(
            (o) => Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(child: Text(o.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))),
                        Chip(label: Text(o.status.replaceAll('_', ' '))),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text('₹${o.total} • ${o.paymentMethod.toUpperCase()} • ${o.paymentStatus}'),
                    if (o.paymentMethod == 'upi' && o.paymentStatus != 'paid' && o.status != 'cancelled') ...[
                      const SizedBox(height: 10),
                      FilledButton.icon(
                        onPressed: payingOrderId == o.id ? null : () => pay(o),
                        icon: payingOrderId == o.id
                            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.payments_outlined),
                        label: Text(payingOrderId == o.id ? 'Opening payment…' : 'Pay now'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
