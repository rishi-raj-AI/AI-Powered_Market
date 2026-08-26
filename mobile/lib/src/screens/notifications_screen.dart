import 'package:flutter/material.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<NotificationEventModel> items = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await GaonApi.notifications();
      if (!mounted) return;
      setState(() {
        items = data;
        loading = false;
        error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = e.toString();
      });
    }
  }

  IconData _iconFor(String eventType) {
    if (eventType.startsWith('delivery.')) return Icons.delivery_dining;
    if (eventType.contains('cancelled')) return Icons.cancel_outlined;
    if (eventType.contains('delivered')) return Icons.check_circle_outline;
    return Icons.receipt_long_outlined;
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Updates',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          const Text('Order and delivery activity appears here even before push notifications are connected.'),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(40),
              child: Center(child: Text('No updates yet.')),
            ),
          ...items.map(
            (item) => Card(
              child: ListTile(
                leading: CircleAvatar(child: Icon(_iconFor(item.eventType))),
                title: Text(item.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(item.body),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
