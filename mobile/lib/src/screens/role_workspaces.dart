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
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await GaonApi.merchantOrders();
      if (mounted) {
        setState(() {
          orders = data;
          loading = false;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() { loading = false; error = e.toString(); });
    }
  }

  Future<void> update(OrderModel o, String status) async {
    try {
      await GaonApi.updateMerchantOrder(o.id, status);
      await load();
    } catch (e) {
      _snack(e.toString());
    }
  }

  void _snack(String s) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s)));
  }

  List<String> actions(String status) => switch (status) {
        'placed' => ['accepted', 'cancelled'],
        'accepted' => ['preparing', 'cancelled'],
        'preparing' => ['ready'],
        _ => [],
      };

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Merchant workspace'),
          actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: load,
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text('Orders', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 6),
                    const Text('Accept, prepare and hand orders over to the delivery network.'),
                    if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    if (orders.isEmpty) const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No merchant orders.'))),
                    ...orders.map(
                      (o) => Card(
                        child: ListTile(
                          title: Text(o.orderNumber, style: const TextStyle(fontWeight: FontWeight.w700)),
                          subtitle: Text('₹${o.total} • ${o.status.replaceAll('_', ' ')} • ${o.paymentStatus}'),
                          trailing: actions(o.status).isEmpty
                              ? const Icon(Icons.check_circle_outline)
                              : PopupMenuButton<String>(
                                  onSelected: (s) => update(o, s),
                                  itemBuilder: (_) => actions(o.status)
                                      .map((s) => PopupMenuItem(value: s, child: Text(s == 'cancelled' ? 'Cancel order' : 'Mark ${s.replaceAll('_', ' ')}')))
                                      .toList(),
                                ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
      );
}

class DeliveryWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const DeliveryWorkspace({super.key, required this.onLogout});
  @override
  State<DeliveryWorkspace> createState() => _DeliveryWorkspaceState();
}

class _DeliveryWorkspaceState extends State<DeliveryWorkspace> {
  List<DeliveryTaskModel> available = [];
  List<DeliveryTaskModel> mine = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final r = await Future.wait([GaonApi.availableDeliveryTasks(), GaonApi.myDeliveryTasks()]);
      if (mounted) {
        setState(() {
          available = r[0];
          mine = r[1];
          loading = false;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() { loading = false; error = e.toString(); });
    }
  }

  Future<void> claim(String id) async {
    try {
      await GaonApi.claimDelivery(id);
      await load();
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<void> update(DeliveryTaskModel d, String s) async {
    try {
      await GaonApi.updateDelivery(d.id, s);
      await load();
    } catch (e) {
      _snack(e.toString());
    }
  }

  void _snack(String s) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s)));
  }

  Widget _location(String title, String? name, String? landmark, double? lat, double? lng) {
    final coordinate = lat != null && lng != null ? ' • ${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}' : '';
    return Padding(
      padding: const EdgeInsets.only(top: 5),
      child: Text('$title: ${name ?? ''}${name != null && landmark != null ? ' • ' : ''}${landmark ?? 'Location not specified'}$coordinate'),
    );
  }

  Widget _taskCard(DeliveryTaskModel d, {required bool canClaim}) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(d.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))),
                Chip(label: Text(d.status.replaceAll('_', ' '))),
              ],
            ),
            Text('₹${d.total} • ${d.paymentMethod.toUpperCase()} • ${d.paymentStatus}'),
            _location('Pickup', d.storeName, d.storeLandmark, d.storeLatitude, d.storeLongitude),
            _location('Drop', d.recipientName, '${d.houseDetails ?? ''} ${d.customerLandmark}'.trim(), d.customerLatitude, d.customerLongitude),
            if (d.recipientPhone != null) Text('Customer: ${d.recipientPhone}'),
            if (d.customerDirections != null && d.customerDirections!.isNotEmpty) Text('Directions: ${d.customerDirections}'),
            const SizedBox(height: 12),
            if (canClaim)
              FilledButton.icon(onPressed: () => claim(d.id), icon: const Icon(Icons.delivery_dining), label: const Text('Claim delivery'))
            else if (d.status == 'assigned')
              FilledButton(onPressed: () => update(d, 'picked_up'), child: const Text('Mark picked up'))
            else if (d.status == 'picked_up')
              FilledButton(onPressed: () => update(d, 'delivered'), child: const Text('Mark delivered'))
            else
              const Align(alignment: Alignment.centerRight, child: Icon(Icons.check_circle_outline)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Delivery workspace'),
          actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: load,
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text('Available jobs', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                    if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    if (available.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 14), child: Text('No unassigned deliveries right now.')),
                    ...available.map((d) => _taskCard(d, canClaim: true)),
                    const SizedBox(height: 18),
                    Text('My deliveries', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                    ...mine.map((d) => _taskCard(d, canClaim: false)),
                  ],
                ),
              ),
      );
}

class AdminWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const AdminWorkspace({super.key, required this.onLogout});
  @override
  State<AdminWorkspace> createState() => _AdminWorkspaceState();
}

class _AdminWorkspaceState extends State<AdminWorkspace> {
  List<OrderModel> orders = [];
  bool loading = true;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await GaonApi.merchantOrders();
      if (mounted) setState(() { orders = data; loading = false; });
    } catch (_) {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('GaonOne admin'),
          actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: load,
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text('Operations', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                    Text('${orders.length} total orders visible'),
                    const SizedBox(height: 12),
                    const Card(child: ListTile(leading: Icon(Icons.desktop_windows_outlined), title: Text('Use the web admin workspace for merchant approvals, catalogue and full operational controls.'))),
                    ...orders.take(20).map((o) => Card(child: ListTile(title: Text(o.orderNumber), subtitle: Text('${o.status} • ₹${o.total} • ${o.paymentStatus}')))),
                  ],
                ),
              ),
      );
}
