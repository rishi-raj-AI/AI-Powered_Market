import 'package:flutter/material.dart';

import '../api/commerce_intelligence_api.dart';

class StoreTrustCard extends StatefulWidget {
  final String storeId;
  const StoreTrustCard({super.key, required this.storeId});

  @override
  State<StoreTrustCard> createState() => _StoreTrustCardState();
}

class _StoreTrustCardState extends State<StoreTrustCard> {
  Map<String, dynamic>? result;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final next = await CommerceIntelligenceApi.merchantReliability(widget.storeId);
      if (mounted) setState(() => result = next);
    } catch (exception) {
      if (mounted) {
        setState(() => error = '$exception'.replaceFirst('Exception: ', ''));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = result;
    if (error != null) {
      return const Card(
        child: ListTile(
          leading: Icon(Icons.shield_outlined),
          title: Text('Store fulfilment history unavailable'),
          subtitle: Text('This does not block ordering. Pull to refresh later.'),
        ),
      );
    }
    if (current == null) {
      return const Card(
        child: ListTile(
          leading: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          title: Text('Loading store fulfilment history…'),
        ),
      );
    }
    final score = (((current['score'] as num?) ?? 0.5) * 100).round();
    final confidence = current['confidence'] as String? ?? 'low';
    return Card(
      child: ListTile(
        leading: const Icon(Icons.shield_outlined),
        title: Text(CommerceIntelligenceApi.trustLabel(current)),
        subtitle: Text(CommerceIntelligenceApi.trustDetail(current)),
        trailing: confidence == 'low' ? null : Text('$score%'),
      ),
    );
  }
}
