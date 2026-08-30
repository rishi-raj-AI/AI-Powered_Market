import 'package:flutter/material.dart';

import '../api/commerce_intelligence_api.dart';

class FulfillmentWindowsCard extends StatefulWidget {
  final String storeId;
  final bool deliveryEnabled;
  final bool pickupEnabled;
  const FulfillmentWindowsCard({super.key, required this.storeId, required this.deliveryEnabled, required this.pickupEnabled});

  @override
  State<FulfillmentWindowsCard> createState() => _FulfillmentWindowsCardState();
}

class _FulfillmentWindowsCardState extends State<FulfillmentWindowsCard> {
  List<Map<String, dynamic>> items = [];
  bool loading = false;
  String? error;
  late String mode;

  @override
  void initState() { super.initState(); mode = widget.deliveryEnabled ? 'delivery' : 'pickup'; load(); }

  Future<void> load([String? next]) async {
    if (next != null) mode = next;
    setState(() { loading = true; error = null; });
    try {
      final result = await CommerceIntelligenceApi.fulfillmentWindows(widget.storeId, mode);
      if (mounted) setState(() => items = result);
    } catch (e) {
      if (mounted) setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally { if (mounted) setState(() => loading = false); }
  }

  DateTime indiaTime(String value) => DateTime.parse(value).toUtc().add(const Duration(hours: 5, minutes: 30));
  String label(Map<String, dynamic> item) {
    final start = indiaTime(item['start_at'] as String);
    final end = indiaTime(item['end_at'] as String);
    String two(int n) => n.toString().padLeft(2, '0');
    return '${start.day}/${start.month} ${two(start.hour)}:${two(start.minute)}–${two(end.hour)}:${two(end.minute)} IST';
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.deliveryEnabled && !widget.pickupEnabled) return const SizedBox.shrink();
    return Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Row(children: [Icon(Icons.calendar_month_outlined), SizedBox(width: 8), Text('Upcoming fulfilment windows', style: TextStyle(fontWeight: FontWeight.w700))]),
      const SizedBox(height: 4),
      Text('India-local availability preview. This does not reserve a slot; final checkout revalidates fulfilment.', style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 8),
      SegmentedButton<String>(segments: [if (widget.deliveryEnabled) const ButtonSegment(value: 'delivery', label: Text('Delivery')), if (widget.pickupEnabled) const ButtonSegment(value: 'pickup', label: Text('Pickup'))], selected: {mode}, onSelectionChanged: (value) => load(value.first)),
      if (loading) const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator()),
      if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      if (!loading && error == null && items.isEmpty) const Padding(padding: EdgeInsets.only(top: 8), child: Text('No window is currently available for this mode.')),
      if (items.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Wrap(spacing: 6, runSpacing: 6, children: items.take(6).map((item) => Chip(label: Text(label(item)))).toList())),
    ])));
  }
}
