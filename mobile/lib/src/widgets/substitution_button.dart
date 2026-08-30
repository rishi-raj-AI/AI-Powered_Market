import 'package:flutter/material.dart';

import '../api/commerce_intelligence_api.dart';
import '../api/gaon_api.dart';

class SubstitutionButton extends StatelessWidget {
  final String listingId;
  const SubstitutionButton({super.key, required this.listingId});

  Future<void> showChoices(BuildContext context) async {
    try {
      final items = await CommerceIntelligenceApi.substitutions(listingId);
      if (!context.mounted) return;
      await showModalBottomSheet(
        context: context,
        builder: (sheetContext) => SafeArea(child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Choose an alternative', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const Text('Nothing is substituted automatically. Your chosen item is checked again when added and at checkout.'),
            const SizedBox(height: 8),
            if (items.isEmpty) const ListTile(title: Text('No close same-store alternative is available right now.')),
            ...items.take(4).map((item) => ListTile(
              title: Text(item['name'] as String? ?? 'Alternative'),
              subtitle: Text('${item['unit'] ?? ''} • ₹${item['price']}'),
              trailing: OutlinedButton(onPressed: () async {
                try { await GaonApi.addToCart(item['listing_id'] as String); if (sheetContext.mounted) Navigator.pop(sheetContext); if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${item['name']} added to cart'))); }
                catch (e) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceFirst('Exception: ', '')))); }
              }, child: const Text('Choose')),
            )),
          ]),
        )),
      );
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))));
    }
  }

  @override
  Widget build(BuildContext context) => TextButton.icon(onPressed: () => showChoices(context), icon: const Icon(Icons.swap_horiz), label: const Text('Alternatives'));
}
