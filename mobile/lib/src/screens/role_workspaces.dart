import 'package:flutter/material.dart';
import '../api/gaon_api.dart';
import '../models/models.dart';

class MerchantWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const MerchantWorkspace({super.key, required this.onLogout});
  @override
  State<MerchantWorkspace> createState() => _MerchantWorkspaceState();
}

class _MerchantWorkspaceState extends State<MerchantWorkspace> {
  List<OrderModel> orders = [];
  bool loading = true;
  String? error;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try { final data = await GaonApi.merchantOrders(); if (mounted) setState(() { orders = data; loading = false; error = null; }); }
    catch (e) { if (mounted) setState(() { loading = false; error = e.toString(); }); }
  }
  Future<void> update(OrderModel o, String status) async { try { await GaonApi.updateMerchantOrder(o.id, status); await load(); } catch (e) { _snack(e.toString()); } }
  void _snack(String s) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s))); }
  List<String> actions(String status) => switch (status) { 'placed' => ['accepted'], 'accepted' => ['preparing'], 'preparing' => ['ready'], _ => [] };
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Merchant workspace'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]), body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
    Text('Orders', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
    if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
    if (orders.isEmpty) const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No merchant orders.'))),
    ...orders.map((o) => Card(child: ListTile(title: Text(o.orderNumber), subtitle: Text('₹${o.total} • ${o.status}'), trailing: actions(o.status).isEmpty ? const Icon(Icons.check_circle_outline) : PopupMenuButton<String>(onSelected: (s) => update(o, s), itemBuilder: (_) => actions(o.status).map((s) => PopupMenuItem(value: s, child: Text('Mark ${s.replaceAll('_',' ')}'))).toList()))),
  ])));
}

class DeliveryWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const DeliveryWorkspace({super.key, required this.onLogout});
  @override
  State<DeliveryWorkspace> createState() => _DeliveryWorkspaceState();
}

class _DeliveryWorkspaceState extends State<DeliveryWorkspace> {
  List<DeliveryModel> available = [];
  List<DeliveryModel> mine = [];
  bool loading = true;
  String? error;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try { final r = await Future.wait([GaonApi.availableDeliveries(), GaonApi.myDeliveries()]); if (mounted) setState(() { available = r[0]; mine = r[1]; loading = false; error = null; }); }
    catch (e) { if (mounted) setState(() { loading = false; error = e.toString(); }); }
  }
  Future<void> claim(String id) async { try { await GaonApi.claimDelivery(id); await load(); } catch (e) { _snack(e.toString()); } }
  Future<void> update(DeliveryModel d, String s) async { try { await GaonApi.updateDelivery(d.id, s); await load(); } catch (e) { _snack(e.toString()); } }
  void _snack(String s) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s))); }
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Delivery workspace'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]), body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
    Text('Available jobs', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
    if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
    ...available.map((d) => Card(child: ListTile(title: Text('Order ${d.orderId.substring(0, 8)}'), subtitle: Text(d.status), trailing: FilledButton(onPressed: () => claim(d.id), child: const Text('Claim'))))),
    const SizedBox(height: 18),
    Text('My deliveries', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
    ...mine.map((d) => Card(child: ListTile(title: Text('Order ${d.orderId.substring(0, 8)}'), subtitle: Text(d.status), trailing: d.status == 'assigned' ? FilledButton(onPressed: () => update(d, 'picked_up'), child: const Text('Picked up')) : d.status == 'picked_up' ? FilledButton(onPressed: () => update(d, 'delivered'), child: const Text('Delivered')) : const Icon(Icons.check_circle_outline)))),
  ])));
}
