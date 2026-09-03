import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../api/gaon_api.dart';

class OrderSupportCard extends StatelessWidget {
  final String orderId;
  const OrderSupportCard({super.key, required this.orderId});

  Future<void> _create(BuildContext context) async {
    final description = TextEditingController();
    final submit = await showDialog<bool>(context: context, builder: (dialog) => AlertDialog(title: const Text('Get order help'), content: TextField(controller: description, minLines: 3, maxLines: 6, decoration: const InputDecoration(labelText: 'What happened?')), actions: [TextButton(onPressed: () => Navigator.pop(dialog, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(dialog, true), child: const Text('Create ticket'))]));
    if (submit != true || description.text.trim().length < 5) return;
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    final response = await http.post(Uri.parse('${GaonApi.baseUrl}/support/tickets'), headers: {'Content-Type': 'application/json', if (token != null) 'Authorization': 'Bearer $token'}, body: jsonEncode({'subject': 'Order support', 'description': description.text.trim(), 'order_id': orderId})).timeout(GaonApi.timeout);
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(response.statusCode == 201 ? 'Support ticket created.' : 'Could not create support ticket.')));
  }

  @override
  Widget build(BuildContext context) => Card(child: ListTile(leading: const Icon(Icons.support_agent), title: const Text('Need help with this order?'), subtitle: const Text('Create an ownership-checked support ticket.'), trailing: OutlinedButton(onPressed: () => _create(context), child: const Text('Get help'))));
}
