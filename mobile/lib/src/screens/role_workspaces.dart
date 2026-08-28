import 'package:flutter/material.dart';
import '../api/gaon_api.dart';
import '../models/models.dart';

class MerchantWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const MerchantWorkspace({super.key, required this.onLogout});
  @override State<MerchantWorkspace> createState() => _MerchantWorkspaceState();
}

class _MerchantWorkspaceState extends State<MerchantWorkspace> {
  List<OrderModel> orders = [];
  List<StoreModel> stores = [];
  Map<String, dynamic>? profile;
  bool loading = true;
  String? error;

  @override void initState() { super.initState(); load(); }

  Future<void> load() async {
    try {
      final merchant = await GaonApi.merchantProfile();
      final result = await Future.wait([GaonApi.merchantOrders(), GaonApi.myStores()]);
      if (mounted) setState(() { profile = merchant; orders = result[0] as List<OrderModel>; stores = result[1] as List<StoreModel>; loading = false; error = null; });
    } catch (e) { if (mounted) setState(() { loading = false; error = e.toString(); }); }
  }

  void snack(String message) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message))); }
  List<String> actions(String status) => switch (status) { 'placed' => ['accepted', 'cancelled'], 'accepted' => ['preparing', 'cancelled'], 'preparing' => ['ready'], _ => [] };

  Future<void> update(OrderModel order, String status) async {
    try { await GaonApi.updateMerchantOrder(order.id, status); await load(); } catch (e) { snack('$e'); }
  }

  Future<void> addStore() async {
    final villages = await GaonApi.villages();
    if (!mounted || villages.isEmpty) return;
    final name = TextEditingController();
    final landmark = TextEditingController();
    String village = villages.first.id;
    final ok = await showDialog<bool>(context: context, builder: (dialogContext) => StatefulBuilder(builder: (dialogContext, setDialogState) => AlertDialog(
      title: const Text('Create storefront'),
      content: SizedBox(width: 420, child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: name, decoration: const InputDecoration(labelText: 'Store name')),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(initialValue: village, items: villages.map((item) => DropdownMenuItem(value: item.id, child: Text('${item.name}, ${item.district}'))).toList(), onChanged: (value) { if (value != null) setDialogState(() => village = value); }, decoration: const InputDecoration(labelText: 'Village')),
        const SizedBox(height: 10),
        TextField(controller: landmark, decoration: const InputDecoration(labelText: 'Landmark')),
      ])),
      actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Create'))],
    )));
    if (ok == true && name.text.trim().length > 1) {
      try {
        final slug = '${name.text.trim().toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '-')}-${DateTime.now().millisecondsSinceEpoch}';
        await GaonApi.createStore(villageId: village, name: name.text.trim(), slug: slug, landmark: landmark.text.trim());
        await load();
      } catch (e) { snack('$e'); }
    }
  }

  Future<void> editListing(StoreModel store, StoreProduct listing) async {
    final price = TextEditingController(text: listing.price);
    final mrp = TextEditingController(text: listing.mrp ?? '');
    final stock = TextEditingController(text: '${listing.stock}');
    bool available = listing.isAvailable;
    final ok = await showDialog<bool>(context: context, builder: (dialogContext) => StatefulBuilder(builder: (dialogContext, setDialogState) => AlertDialog(
      title: Text(listing.name),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: price, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Selling price')),
        TextField(controller: mrp, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'MRP')),
        TextField(controller: stock, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Stock quantity')),
        SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Available for customers'), value: available, onChanged: (value) => setDialogState(() => available = value)),
      ]),
      actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Save'))],
    )));
    if (ok == true) {
      final quantity = int.tryParse(stock.text.trim());
      if (double.tryParse(price.text.trim()) == null || quantity == null || quantity < 0) { snack('Enter a valid price and stock quantity.'); return; }
      try {
        await GaonApi.updateStoreProduct(storeId: store.id, listingId: listing.id, price: price.text.trim(), mrp: mrp.text.trim().isEmpty ? null : mrp.text.trim(), stockQuantity: quantity, isAvailable: available);
        if (mounted) Navigator.pop(context);
        await manageInventory(store);
      } catch (e) { snack('$e'); }
    }
  }

  Future<void> addListing(StoreModel store) async {
    final products = await GaonApi.products();
    if (!mounted || products.isEmpty) { snack('No starter products are available.'); return; }
    String productId = products.first.id;
    final price = TextEditingController();
    final stock = TextEditingController(text: '1');
    final ok = await showDialog<bool>(context: context, builder: (dialogContext) => StatefulBuilder(builder: (dialogContext, setDialogState) => AlertDialog(
      title: Text('Add product to ${store.name}'),
      content: SizedBox(width: 460, child: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField<String>(initialValue: productId, isExpanded: true, items: products.map((item) => DropdownMenuItem(value: item.id, child: Text('${item.name} • ${item.unit}', overflow: TextOverflow.ellipsis))).toList(), onChanged: (value) { if (value != null) setDialogState(() => productId = value); }, decoration: const InputDecoration(labelText: 'Product')),
        const SizedBox(height: 10),
        TextField(controller: price, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Selling price')),
        TextField(controller: stock, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Opening stock')),
      ])),
      actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Add product'))],
    )));
    if (ok == true) {
      final quantity = int.tryParse(stock.text.trim());
      if (double.tryParse(price.text.trim()) == null || quantity == null || quantity < 0) { snack('Enter a valid price and stock quantity.'); return; }
      try { await GaonApi.upsertStoreProduct(storeId: store.id, productId: productId, price: price.text.trim(), stockQuantity: quantity); if (mounted) Navigator.pop(context); await manageInventory(store); } catch (e) { snack('$e'); }
    }
  }

  Future<void> manageInventory(StoreModel store) async {
    try {
      final inventory = await GaonApi.storeInventory(store.id);
      if (!mounted) return;
      await showModalBottomSheet<void>(context: context, isScrollControlled: true, builder: (sheetContext) => SafeArea(child: SizedBox(height: MediaQuery.of(sheetContext).size.height * .8, child: Column(children: [
        Padding(padding: const EdgeInsets.fromLTRB(18, 18, 10, 10), child: Row(children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(store.name, style: Theme.of(sheetContext).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)), Text('${inventory.length} catalogue items')])), IconButton(onPressed: () => Navigator.pop(sheetContext), icon: const Icon(Icons.close))])),
        Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: () { Navigator.pop(sheetContext); addListing(store); }, icon: const Icon(Icons.add), label: const Text('Add product')))),
        const SizedBox(height: 8),
        Expanded(child: inventory.isEmpty ? const Center(child: Text('No products listed yet.')) : ListView.builder(itemCount: inventory.length, itemBuilder: (_, index) { final item = inventory[index]; return ListTile(title: Text(item.name), subtitle: Text('₹${item.price} • Stock ${item.stock} • ${item.isAvailable ? 'Visible' : 'Hidden'}'), trailing: const Icon(Icons.edit_outlined), onTap: () { Navigator.pop(sheetContext); editListing(store, item); }); })),
      ]))));
    } catch (e) { snack('$e'); }
  }

  @override Widget build(BuildContext context) {
    final approved = profile?['status'] == 'approved';
    return Scaffold(
      appBar: AppBar(title: const Text('Merchant workspace'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]),
      floatingActionButton: approved ? FloatingActionButton.extended(onPressed: addStore, icon: const Icon(Icons.add_business), label: const Text('Add store')) : null,
      body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
        Text('${profile?['business_name'] ?? 'Merchant operations'}', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
        Text('Status: ${profile?['status'] ?? 'unknown'}'),
        if (profile?['status'] == 'pending') const Card(child: ListTile(leading: Icon(Icons.hourglass_top), title: Text('Approval pending'), subtitle: Text('GaonOne admin will activate storefront operations after verification.'))),
        if (profile?['status'] == 'suspended') const Card(child: ListTile(leading: Icon(Icons.block), title: Text('Merchant access suspended'))),
        if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        const SizedBox(height: 14),
        Text('Stores (${stores.length})', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
        ...stores.map((store) => Card(child: ListTile(leading: const Icon(Icons.storefront), title: Text(store.name), subtitle: Text('${store.landmark ?? 'Local storefront'}\nTap to manage catalogue and stock'), isThreeLine: true, trailing: const Icon(Icons.inventory_2_outlined), onTap: approved ? () => manageInventory(store) : null))),
        const SizedBox(height: 14),
        Text('Orders', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
        if (orders.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Text('No merchant orders yet.')),
        ...orders.map((order) => Card(child: ListTile(title: Text(order.orderNumber), subtitle: Text('₹${order.total} • ${order.status.replaceAll('_', ' ')} • ${order.paymentStatus}'), trailing: actions(order.status).isEmpty ? const Icon(Icons.check_circle_outline) : PopupMenuButton<String>(onSelected: (status) => update(order, status), itemBuilder: (_) => actions(order.status).map((status) => PopupMenuItem(value: status, child: Text(status == 'cancelled' ? 'Cancel order' : 'Mark ${status.replaceAll('_', ' ')}'))).toList())))),
      ])),
    );
  }
}

class DeliveryWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const DeliveryWorkspace({super.key, required this.onLogout});
  @override State<DeliveryWorkspace> createState() => _DeliveryWorkspaceState();
}

class _DeliveryWorkspaceState extends State<DeliveryWorkspace> {
  List<DeliveryTaskModel> available = [], mine = [];
  bool loading = true;
  String? error;
  @override void initState() { super.initState(); load(); }
  Future<void> load() async { try { final result = await Future.wait([GaonApi.availableDeliveryTasks(), GaonApi.myDeliveryTasks()]); if (mounted) setState(() { available = result[0]; mine = result[1]; loading = false; error = null; }); } catch (e) { if (mounted) setState(() { loading = false; error = '$e'; }); } }
  Future<void> claim(String id) async { try { await GaonApi.claimDelivery(id); await load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); } }
  Future<void> update(DeliveryTaskModel task, String status) async { try { await GaonApi.updateDelivery(task.id, status); await load(); } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); } }
  Widget card(DeliveryTaskModel task, bool canClaim) => Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(children: [Expanded(child: Text(task.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))), Chip(label: Text(task.status.replaceAll('_', ' ')))]),
    Text('₹${task.total} • ${task.paymentMethod.toUpperCase()} • ${task.paymentStatus}'),
    Text('Pickup: ${task.storeName} • ${task.storeLandmark ?? 'location pending'}'),
    Text('Drop: ${task.recipientName ?? 'Customer'} • ${task.customerLandmark}'),
    if (task.recipientPhone != null) SelectableText('Customer: ${task.recipientPhone}'),
    if (task.customerDirections?.isNotEmpty == true) Text('Directions: ${task.customerDirections}'),
    const SizedBox(height: 10),
    if (canClaim) FilledButton.icon(onPressed: () => claim(task.id), icon: const Icon(Icons.delivery_dining), label: const Text('Claim delivery'))
    else if (task.status == 'assigned') FilledButton(onPressed: () => update(task, 'picked_up'), child: const Text('Mark picked up'))
    else if (task.status == 'picked_up') FilledButton(onPressed: () => update(task, 'delivered'), child: const Text('Mark delivered')),
  ])));

  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Delivery workspace'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]),
    body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
      Text('Delivery network', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      const Text('Claim ready jobs, collect COD where shown, and update each hand-off immediately.'),
      if (error != null) Text(error!),
      const SizedBox(height: 16),
      Text('Available jobs (${available.length})', style: Theme.of(context).textTheme.titleLarge), ...available.map((task) => card(task, true)),
      const SizedBox(height: 16),
      Text('My deliveries (${mine.length})', style: Theme.of(context).textTheme.titleLarge), ...mine.map((task) => card(task, false)),
    ])),
  );
}

class AdminWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const AdminWorkspace({super.key, required this.onLogout});
  @override State<AdminWorkspace> createState() => _AdminWorkspaceState();
}

class _AdminWorkspaceState extends State<AdminWorkspace> {
  List<OrderModel> orders = [];
  bool loading = true;
  @override void initState() { super.initState(); load(); }
  Future<void> load() async { try { final data = await GaonApi.merchantOrders(); if (mounted) setState(() { orders = data; loading = false; }); } catch (_) { if (mounted) setState(() => loading = false); } }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('GaonOne admin'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]),
    body: loading ? const Center(child: CircularProgressIndicator()) : RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.all(16), children: [
      Text('Pilot operations', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      Text('${orders.length} orders visible'),
      const Card(child: ListTile(leading: Icon(Icons.desktop_windows_outlined), title: Text('Use the web admin command centre for merchant approvals, rider activation and push dispatch.'))),
      ...orders.take(20).map((order) => Card(child: ListTile(title: Text(order.orderNumber), subtitle: Text('${order.status} • ₹${order.total} • ${order.paymentStatus}')))),
    ])),
  );
}
