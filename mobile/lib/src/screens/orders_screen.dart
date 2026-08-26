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

  @override
  void initState() { super.initState(); load(); }

  Future<void> load() async {
    try { final data = await GaonApi.orders(); if (mounted) setState(() { orders = data; loading = false; error = null; }); }
    catch (e) { if (mounted) setState(() { loading = false; error = e.toString(); }); }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    return RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
      Text('My orders', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text(error!, style: const TextStyle(color: Colors.red))),
      if (orders.isEmpty) const Padding(padding: EdgeInsets.all(40), child: Center(child: Text('No orders yet.'))),
      ...orders.map((o) => Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Expanded(child: Text(o.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))), Chip(label: Text(o.status.replaceAll('_', ' ')))]),
        const SizedBox(height: 6),
        Text('₹${o.total} • ${o.paymentMethod.toUpperCase()} • ${o.paymentStatus}'),
      ]))),
    ]));
  }
}
