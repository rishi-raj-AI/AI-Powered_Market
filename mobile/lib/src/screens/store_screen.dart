import 'package:flutter/material.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

class StoreScreen extends StatefulWidget {
  final StoreModel store;

  const StoreScreen({super.key, required this.store});

  @override
  State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  List<StoreProduct> products = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result = await GaonApi.storeProducts(widget.store.id);
      if (!mounted) return;
      setState(() {
        products = result;
        loading = false;
        error = null;
      });
    } catch (exception) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = exception.toString();
      });
    }
  }

  Future<void> addToCart(StoreProduct product) async {
    try {
      await GaonApi.addToCart(product.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${product.name} added to cart')),
      );
    } catch (exception) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(exception.toString())),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.store.name)),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: load,
              child: ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: error == null ? products.length : products.length + 1,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  if (error != null && index == 0) {
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          error!,
                          style: const TextStyle(color: Colors.red),
                        ),
                      ),
                    );
                  }

                  final productIndex = error == null ? index : index - 1;
                  final product = products[productIndex];

                  return Card(
                    child: ListTile(
                      title: Text(
                        product.name,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      subtitle: Text('${product.unit} • ${product.stock} in stock'),
                      trailing: FilledButton(
                        onPressed: product.stock <= 0
                            ? null
                            : () => addToCart(product),
                        child: Text('₹${product.price} +'),
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
