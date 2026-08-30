import 'package:flutter/material.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

class MerchantWorkspace extends StatefulWidget {
  final VoidCallback onLogout;

  const MerchantWorkspace({super.key, required this.onLogout});

  @override
  State<MerchantWorkspace> createState() => _MerchantWorkspaceState();
}

class _InventoryRow {
  final StoreModel store;
  final StoreProduct listing;

  const _InventoryRow(this.store, this.listing);
}

class _MerchantWorkspaceState extends State<MerchantWorkspace> {
  Map<String, dynamic>? profile;
  List<OrderModel> orders = [];
  List<StoreModel> stores = [];
  List<_InventoryRow> inventory = [];
  bool loading = true;
  String? error;
  String orderFilter = 'active';

  bool get approved => profile?['status'] == 'approved';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final merchant = await GaonApi.merchantProfile();
      final results = await Future.wait([
        GaonApi.merchantOrders(),
        GaonApi.myStores(),
      ]);
      final loadedStores = results[1] as List<StoreModel>;
      final inventoryResults = await Future.wait(
        loadedStores.map((store) async {
          try {
            final listings = await GaonApi.storeInventory(store.id);
            return listings.map((item) => _InventoryRow(store, item)).toList();
          } catch (_) {
            return <_InventoryRow>[];
          }
        }),
      );
      if (!mounted) return;
      setState(() {
        profile = merchant;
        orders = results[0] as List<OrderModel>;
        stores = loadedStores;
        inventory = inventoryResults.expand((items) => items).toList();
        loading = false;
        error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  void snack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message.replaceFirst('Exception: ', ''))),
    );
  }

  List<String> actionsFor(String status) => switch (status) {
        'placed' => ['accepted', 'cancelled'],
        'accepted' => ['preparing', 'cancelled'],
        'preparing' => ['ready'],
        _ => [],
      };

  List<OrderModel> get filteredOrders {
    if (orderFilter == 'all') return orders;
    if (orderFilter == 'new') return orders.where((order) => order.status == 'placed').toList();
    if (orderFilter == 'ready') return orders.where((order) => order.status == 'ready').toList();
    const active = {'placed', 'accepted', 'preparing', 'ready'};
    return orders.where((order) => active.contains(order.status)).toList();
  }

  Future<void> updateOrder(OrderModel order, String status) async {
    try {
      await GaonApi.updateMerchantOrder(order.id, status);
      await load();
      snack('Order ${order.orderNumber} updated to ${status.replaceAll('_', ' ')}.');
    } catch (e) {
      snack('$e');
    }
  }

  Future<void> showOrder(OrderModel order) async {
    try {
      final detail = await GaonApi.orderDetail(order.id);
      if (!mounted) return;
      final items = detail['items'] as List? ?? const [];
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (sheetContext) => SafeArea(
          child: FractionallySizedBox(
            heightFactor: .86,
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              order.orderNumber,
                              style: Theme.of(sheetContext)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(fontWeight: FontWeight.w800),
                            ),
                            Text('${detail['store_name'] ?? 'Store'} • ${order.status.replaceAll('_', ' ')}'),
                          ],
                        ),
                      ),
                      IconButton(onPressed: () => Navigator.pop(sheetContext), icon: const Icon(Icons.close)),
                    ],
                  ),
                  const Divider(),
                  Expanded(
                    child: ListView(
                      children: [
                        ...items.map(
                          (item) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text('${item['product_name'] ?? 'Item'}'),
                            subtitle: Text('${item['quantity']} × ₹${item['unit_price']}'),
                            trailing: Text('₹${item['line_total']}'),
                          ),
                        ),
                        const Divider(),
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.location_on_outlined),
                          title: Text('${detail['recipient_name'] ?? 'Customer'}'),
                          subtitle: Text(
                            '${detail['house_details'] ?? ''} ${detail['customer_landmark'] ?? ''}'.trim(),
                          ),
                        ),
                        if (detail['customer_directions'] != null)
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.directions_outlined),
                            title: const Text('Delivery directions'),
                            subtitle: Text('${detail['customer_directions']}'),
                          ),
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.payments_outlined),
                          title: Text('${order.paymentMethod.toUpperCase()} • ${order.paymentStatus}'),
                          trailing: Text(
                            '₹${order.total}',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (actionsFor(order.status).isNotEmpty)
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: actionsFor(order.status)
                          .map(
                            (status) => status == 'cancelled'
                                ? OutlinedButton.icon(
                                    onPressed: () {
                                      Navigator.pop(sheetContext);
                                      updateOrder(order, status);
                                    },
                                    icon: const Icon(Icons.cancel_outlined),
                                    label: const Text('Cancel order'),
                                  )
                                : FilledButton(
                                    onPressed: () {
                                      Navigator.pop(sheetContext);
                                      updateOrder(order, status);
                                    },
                                    child: Text(
                                      status == 'accepted'
                                          ? 'Accept order'
                                          : status == 'preparing'
                                              ? 'Start preparing'
                                              : 'Mark ready',
                                    ),
                                  ),
                          )
                          .toList(),
                    ),
                ],
              ),
            ),
          ),
        ),
      );
    } catch (e) {
      snack('$e');
    }
  }

  Future<void> editListing(_InventoryRow row) async {
    final listing = row.listing;
    final price = TextEditingController(text: listing.price);
    final mrp = TextEditingController(text: listing.mrp ?? '');
    final stock = TextEditingController(text: '${listing.stock}');
    bool available = listing.isAvailable;

    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: Text(listing.name),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(row.store.name, style: Theme.of(dialogContext).textTheme.bodySmall),
                const SizedBox(height: 12),
                TextField(
                  controller: price,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Selling price'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: mrp,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'MRP'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: stock,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Stock quantity'),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Visible to customers'),
                  value: available,
                  onChanged: (value) => setDialogState(() => available = value),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Save')),
          ],
        ),
      ),
    );

    if (ok != true) return;
    final quantity = int.tryParse(stock.text.trim());
    if (double.tryParse(price.text.trim()) == null || quantity == null || quantity < 0) {
      snack('Enter a valid price and stock quantity.');
      return;
    }
    try {
      await GaonApi.updateStoreProduct(
        storeId: row.store.id,
        listingId: listing.id,
        price: price.text.trim(),
        mrp: mrp.text.trim().isEmpty ? null : mrp.text.trim(),
        stockQuantity: quantity,
        isAvailable: available && quantity > 0,
      );
      await load();
    } catch (e) {
      snack('$e');
    }
  }

  Future<void> addListing(StoreModel store) async {
    try {
      final products = await GaonApi.products();
      if (!mounted || products.isEmpty) {
        snack('No catalogue products are available.');
        return;
      }
      String productId = products.first.id;
      final price = TextEditingController();
      final stock = TextEditingController(text: '1');
      final ok = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (dialogContext, setDialogState) => AlertDialog(
            title: Text('Add product to ${store.name}'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: productId,
                    isExpanded: true,
                    items: products
                        .map(
                          (item) => DropdownMenuItem(
                            value: item.id,
                            child: Text('${item.name} • ${item.unit}', overflow: TextOverflow.ellipsis),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) setDialogState(() => productId = value);
                    },
                    decoration: const InputDecoration(labelText: 'Product'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: price,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Selling price'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: stock,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Opening stock'),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Add product')),
            ],
          ),
        ),
      );
      if (ok != true) return;
      final quantity = int.tryParse(stock.text.trim());
      if (double.tryParse(price.text.trim()) == null || quantity == null || quantity < 0) {
        snack('Enter a valid price and stock quantity.');
        return;
      }
      await GaonApi.upsertStoreProduct(
        storeId: store.id,
        productId: productId,
        price: price.text.trim(),
        stockQuantity: quantity,
      );
      await load();
    } catch (e) {
      snack('$e');
    }
  }

  Future<void> manageInventory(StoreModel store) async {
    String query = '';
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final rows = inventory.where((row) => row.store.id == store.id).where((row) {
            final normalized = query.trim().toLowerCase();
            return normalized.isEmpty || row.listing.name.toLowerCase().contains(normalized);
          }).toList();
          return SafeArea(
            child: FractionallySizedBox(
              heightFactor: .88,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            store.name,
                            style: Theme.of(sheetContext)
                                .textTheme
                                .titleLarge
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                        ),
                        IconButton(onPressed: () => Navigator.pop(sheetContext), icon: const Icon(Icons.close)),
                      ],
                    ),
                    TextField(
                      decoration: const InputDecoration(prefixIcon: Icon(Icons.search), labelText: 'Search inventory'),
                      onChanged: (value) => setSheetState(() => query = value),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: () {
                          Navigator.pop(sheetContext);
                          addListing(store);
                        },
                        icon: const Icon(Icons.add),
                        label: const Text('Add product'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Expanded(
                      child: rows.isEmpty
                          ? const Center(child: Text('No matching inventory items.'))
                          : ListView.builder(
                              itemCount: rows.length,
                              itemBuilder: (_, index) {
                                final row = rows[index];
                                final low = row.listing.stock <= 5;
                                return Card(
                                  child: ListTile(
                                    leading: Icon(
                                      low ? Icons.warning_amber_rounded : Icons.inventory_2_outlined,
                                    ),
                                    title: Text(row.listing.name),
                                    subtitle: Text(
                                      '₹${row.listing.price} • Stock ${row.listing.stock} • ${row.listing.isAvailable ? 'Visible' : 'Hidden'}',
                                    ),
                                    trailing: const Icon(Icons.edit_outlined),
                                    onTap: () {
                                      Navigator.pop(sheetContext);
                                      editListing(row);
                                    },
                                  ),
                                );
                              },
                            ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Future<void> addStore() async {
    try {
      final villages = await GaonApi.villages();
      if (!mounted || villages.isEmpty) return;
      String villageId = villages.first.id;
      final name = TextEditingController();
      final landmark = TextEditingController();
      final ok = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (dialogContext, setDialogState) => AlertDialog(
            title: const Text('Create storefront'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(controller: name, decoration: const InputDecoration(labelText: 'Store name')),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    initialValue: villageId,
                    items: villages
                        .map(
                          (village) => DropdownMenuItem(
                            value: village.id,
                            child: Text('${village.name}, ${village.district}'),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) setDialogState(() => villageId = value);
                    },
                    decoration: const InputDecoration(labelText: 'Village'),
                  ),
                  const SizedBox(height: 10),
                  TextField(controller: landmark, decoration: const InputDecoration(labelText: 'Landmark')),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Create')),
            ],
          ),
        ),
      );
      if (ok != true || name.text.trim().length < 2) return;
      final slug = '${name.text.trim().toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '-')}-${DateTime.now().millisecondsSinceEpoch}';
      await GaonApi.createStore(
        villageId: villageId,
        name: name.text.trim(),
        slug: slug,
        landmark: landmark.text.trim(),
      );
      await load();
    } catch (e) {
      snack('$e');
    }
  }

  Widget metric(String label, String value, IconData icon) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon),
              const SizedBox(height: 8),
              Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
              Text(label),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final newOrders = orders.where((order) => order.status == 'placed').length;
    final readyOrders = orders.where((order) => order.status == 'ready').length;
    final lowStock = inventory.where((row) => row.listing.isAvailable && row.listing.stock <= 5).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Merchant operations'),
        actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))],
      ),
      floatingActionButton: approved
          ? FloatingActionButton.extended(
              onPressed: addStore,
              icon: const Icon(Icons.add_business),
              label: const Text('Add store'),
            )
          : null,
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    '${profile?['business_name'] ?? 'Merchant'}',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w900),
                  ),
                  Text('Status: ${profile?['status'] ?? 'unknown'}'),
                  if (profile?['status'] == 'pending')
                    const Card(
                      child: ListTile(
                        leading: Icon(Icons.hourglass_top),
                        title: Text('Approval pending'),
                        subtitle: Text('Store and order operations activate after verification.'),
                      ),
                    ),
                  if (profile?['status'] == 'suspended')
                    const Card(
                      child: ListTile(
                        leading: Icon(Icons.block),
                        title: Text('Merchant access suspended'),
                      ),
                    ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      metric('New orders', '$newOrders', Icons.notifications_active_outlined),
                      metric('Ready', '$readyOrders', Icons.delivery_dining_outlined),
                      metric('Low stock', '$lowStock', Icons.warning_amber_rounded),
                    ],
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Order queue',
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                        ),
                      ),
                      DropdownButton<String>(
                        value: orderFilter,
                        items: const [
                          DropdownMenuItem(value: 'active', child: Text('Active')),
                          DropdownMenuItem(value: 'new', child: Text('New')),
                          DropdownMenuItem(value: 'ready', child: Text('Ready')),
                          DropdownMenuItem(value: 'all', child: Text('All')),
                        ],
                        onChanged: (value) => setState(() => orderFilter = value ?? 'active'),
                      ),
                    ],
                  ),
                  if (filteredOrders.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Center(child: Text('No orders in this queue.')),
                    ),
                  ...filteredOrders.map(
                    (order) => Card(
                      child: ListTile(
                        onTap: () => showOrder(order),
                        title: Text(order.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800)),
                        subtitle: Text(
                          '₹${order.total} • ${order.status.replaceAll('_', ' ')} • ${order.paymentStatus}',
                        ),
                        trailing: actionsFor(order.status).isEmpty
                            ? const Icon(Icons.chevron_right)
                            : PopupMenuButton<String>(
                                onSelected: (status) => updateOrder(order, status),
                                itemBuilder: (_) => actionsFor(order.status)
                                    .map(
                                      (status) => PopupMenuItem(
                                        value: status,
                                        child: Text(
                                          status == 'cancelled'
                                              ? 'Cancel order'
                                              : status == 'accepted'
                                                  ? 'Accept order'
                                                  : status == 'preparing'
                                                      ? 'Start preparing'
                                                      : 'Mark ready',
                                        ),
                                      ),
                                    )
                                    .toList(),
                              ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    'Stores & inventory',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  ...stores.map(
                    (store) {
                      final rows = inventory.where((row) => row.store.id == store.id).toList();
                      final low = rows.where((row) => row.listing.isAvailable && row.listing.stock <= 5).length;
                      return Card(
                        child: ListTile(
                          leading: const Icon(Icons.storefront),
                          title: Text(store.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                          subtitle: Text('${rows.length} products • $low low-stock'),
                          trailing: const Icon(Icons.inventory_2_outlined),
                          onTap: approved ? () => manageInventory(store) : null,
                        ),
                      );
                    },
                  ),
                  if (stores.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(20),
                      child: Text('Create your first storefront after approval.'),
                    ),
                  const SizedBox(height: 80),
                ],
              ),
            ),
    );
  }
}
