import 'package:flutter/material.dart';

import '../api/admin_api.dart';

class AdminOperationsConsole extends StatefulWidget {
  final VoidCallback onLogout;
  const AdminOperationsConsole({super.key, required this.onLogout});

  @override
  State<AdminOperationsConsole> createState() => _AdminOperationsConsoleState();
}

class _AdminOperationsConsoleState extends State<AdminOperationsConsole> {
  Map<String, dynamic> overview = {};
  List<Map<String, dynamic>> users = [];
  List<Map<String, dynamic>> deliveries = [];
  bool loading = true;
  String? error;
  String userQuery = '';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final results = await Future.wait([AdminApi.overview(), AdminApi.users(), AdminApi.activeDeliveries()]);
      if (!mounted) return;
      setState(() {
        overview = results[0] as Map<String, dynamic>;
        users = results[1] as List<Map<String, dynamic>>;
        deliveries = results[2] as List<Map<String, dynamic>>;
        loading = false;
        error = null;
      });
    } catch (e) {
      if (mounted) setState(() { loading = false; error = '$e'; });
    }
  }

  void snack(String message) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Widget metric(String label, Object? value, IconData icon) {
    return SizedBox(
      width: 170,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(icon),
            const SizedBox(height: 10),
            Text('${value ?? 0}', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
            Text(label),
          ]),
        ),
      ),
    );
  }

  Future<void> editUser(Map<String, dynamic> user) async {
    String role = '${user['role']}';
    bool active = user['is_active'] == true;
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: Text(user['full_name'] ?? user['phone'] ?? 'User'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              initialValue: role,
              decoration: const InputDecoration(labelText: 'Role'),
              items: const [
                DropdownMenuItem(value: 'customer', child: Text('Customer')),
                DropdownMenuItem(value: 'merchant', child: Text('Merchant')),
                DropdownMenuItem(value: 'delivery', child: Text('Delivery partner')),
                DropdownMenuItem(value: 'admin', child: Text('Admin')),
              ],
              onChanged: (value) => setDialogState(() => role = value ?? role),
            ),
            SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Account active'), value: active, onChanged: (value) => setDialogState(() => active = value)),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Save')),
          ],
        ),
      ),
    );
    if (ok == true) {
      try {
        await AdminApi.updateUserRole('${user['id']}', role: role, isActive: active);
        await load();
      } catch (e) { snack('$e'); }
    }
  }

  Future<void> unassign(Map<String, dynamic> delivery) async {
    try {
      await AdminApi.unassign('${delivery['id']}');
      await load();
    } catch (e) { snack('$e'); }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    final merchants = Map<String, dynamic>.from(overview['merchants'] ?? {});
    final orders = Map<String, dynamic>.from(overview['orders'] ?? {});
    final operations = Map<String, dynamic>.from(overview['operations'] ?? {});
    final filteredUsers = users.where((user) {
      final haystack = '${user['full_name'] ?? ''} ${user['phone'] ?? ''} ${user['role'] ?? ''}'.toLowerCase();
      return haystack.contains(userQuery.toLowerCase());
    }).toList();

    return Scaffold(
      appBar: AppBar(title: const Text('GaonOne operations'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]),
      body: RefreshIndicator(
        onRefresh: load,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Text('Command centre', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w900)),
          const Text('Operational health, delivery activity and access control.'),
          if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            metric('Users', overview['users'], Icons.people_outline),
            metric('Orders', orders['total'], Icons.receipt_long_outlined),
            metric('Active stores', overview['active_stores'], Icons.storefront_outlined),
            metric('Pending merchants', merchants['pending'], Icons.pending_actions_outlined),
            metric('Ready / unassigned', operations['ready_unassigned_deliveries'], Icons.delivery_dining_outlined),
            metric('Low stock', operations['low_stock_listings'], Icons.inventory_2_outlined),
          ]),
          const SizedBox(height: 20),
          Text('Active deliveries (${deliveries.length})', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          if (deliveries.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Text('No active deliveries right now.')),
          ...deliveries.map((delivery) => Card(
            child: ListTile(
              leading: const Icon(Icons.local_shipping_outlined),
              title: Text(delivery['order_number'] ?? 'Delivery'),
              subtitle: Text('${delivery['store_name'] ?? 'Store'} → ${delivery['customer_landmark'] ?? 'Customer'}\nRider: ${delivery['rider_name'] ?? delivery['rider_phone'] ?? 'Unassigned'} • ${delivery['status']}'),
              isThreeLine: true,
              trailing: delivery['status'] == 'assigned' ? PopupMenuButton<String>(onSelected: (_) => unassign(delivery), itemBuilder: (_) => const [PopupMenuItem(value: 'unassign', child: Text('Unassign before pickup'))]) : null,
            ),
          )),
          const SizedBox(height: 20),
          Text('User & role administration', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          TextField(onChanged: (value) => setState(() => userQuery = value), decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search user, phone or role')),
          const SizedBox(height: 8),
          ...filteredUsers.take(100).map((user) => Card(
            child: ListTile(
              leading: CircleAvatar(child: Text('${user['role'] ?? '?'}'.substring(0, 1).toUpperCase())),
              title: Text(user['full_name'] ?? user['phone'] ?? 'User'),
              subtitle: Text('${user['phone'] ?? ''} • ${user['role']} • ${user['is_active'] == true ? 'active' : 'inactive'}${user['is_super_admin'] == true ? ' • super admin' : ''}'),
              trailing: const Icon(Icons.manage_accounts_outlined),
              onTap: () => editUser(user),
            ),
          )),
          const SizedBox(height: 16),
          Card(child: ListTile(leading: const Icon(Icons.language), title: const Text('Full merchant approval and settlement workflows remain available in the web admin command centre.'))),
        ]),
      ),
    );
  }
}
