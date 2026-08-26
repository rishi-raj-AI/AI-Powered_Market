import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key});
  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  CartModel? cart;
  List<AddressModel> addresses = [];
  List<Village> villages = [];
  bool loading = true;
  bool locating = false;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final results = await Future.wait([GaonApi.cart(), GaonApi.addresses(), GaonApi.villages()]);
      if (!mounted) return;
      setState(() {
        cart = results[0] as CartModel;
        addresses = results[1] as List<AddressModel>;
        villages = results[2] as List<Village>;
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

  Future<void> remove(String storeProductId) async {
    try {
      cart = await GaonApi.removeCartItem(storeProductId);
      if (mounted) setState(() {});
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<Position?> _currentPosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      _snack('Location services are switched off. You can still save the landmark manually.');
      return null;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      _snack('Location permission was not granted. Landmark-only address will still work.');
      return null;
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
    );
  }

  Future<void> addAddress() async {
    if (villages.isEmpty) return;
    String villageId = villages.first.id;
    final label = TextEditingController(text: 'Home');
    final house = TextEditingController();
    final landmark = TextEditingController();
    final directions = TextEditingController();
    Position? position;

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('Add delivery address'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: villageId,
                  items: villages.map((v) => DropdownMenuItem(value: v.id, child: Text(v.name))).toList(),
                  onChanged: (v) => setLocal(() => villageId = v ?? villageId),
                ),
                const SizedBox(height: 10),
                TextField(controller: label, decoration: const InputDecoration(labelText: 'Label')),
                const SizedBox(height: 10),
                TextField(controller: house, decoration: const InputDecoration(labelText: 'House / locality')),
                const SizedBox(height: 10),
                TextField(controller: landmark, decoration: const InputDecoration(labelText: 'Landmark *')),
                const SizedBox(height: 10),
                TextField(controller: directions, decoration: const InputDecoration(labelText: 'Delivery directions')),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: locating
                      ? null
                      : () async {
                          setLocal(() => locating = true);
                          position = await _currentPosition();
                          setLocal(() => locating = false);
                        },
                  icon: const Icon(Icons.my_location),
                  label: Text(position == null ? 'Attach GPS location' : 'GPS location attached'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save')),
          ],
        ),
      ),
    );

    if (ok == true && landmark.text.trim().isNotEmpty) {
      try {
        await GaonApi.createAddress(
          villageId: villageId,
          label: label.text.trim(),
          landmark: landmark.text.trim(),
          houseDetails: house.text.trim(),
          directions: directions.text.trim(),
          latitude: position?.latitude,
          longitude: position?.longitude,
        );
        await load();
      } catch (e) {
        _snack(e.toString());
      }
    }
  }

  Future<void> checkout(AddressModel address, String payment) async {
    try {
      final order = await GaonApi.checkout(address.id, payment);
      if (!mounted) return;
      if (payment == 'upi') {
        final paid = await GaonApi.openRazorpayCheckout(order);
        if (!mounted) return;
        if (!paid) {
          _snack('Order placed, but online payment is still pending. You can retry from Orders.');
        }
      } else {
        await showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Order placed'),
            content: Text('Order ${order.orderNumber}\nTotal ₹${order.total}\nPayment: Cash on delivery'),
            actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
          ),
        );
      }
      await load();
    } catch (e) {
      _snack(e.toString());
    }
  }

  void _snack(String text) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    final c = cart;
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Your cart', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (c == null || c.items.isEmpty)
            const Padding(padding: EdgeInsets.all(40), child: Center(child: Text('Your cart is empty.'))),
          if (c != null)
            ...c.items.map(
              (item) => Card(
                child: ListTile(
                  title: Text(item.product.name),
                  subtitle: Text('${item.quantity} × ₹${item.product.price}'),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => remove(item.product.id),
                  ),
                ),
              ),
            ),
          if (c != null && c.items.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('Subtotal ₹${c.subtotal}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(child: Text('Delivery address', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
                TextButton.icon(onPressed: addAddress, icon: const Icon(Icons.add), label: const Text('Add')),
              ],
            ),
            if (addresses.isEmpty) const Text('Add an address before checkout.'),
            ...addresses.map(
              (a) => Card(
                child: ListTile(
                  leading: Icon(a.latitude != null ? Icons.location_on : Icons.signpost_outlined),
                  title: Text(a.label),
                  subtitle: Text('${a.houseDetails ?? ''} • ${a.landmark}'),
                  trailing: PopupMenuButton<String>(
                    onSelected: (p) => checkout(a, p),
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'cod', child: Text('Cash on delivery')),
                      PopupMenuItem(value: 'upi', child: Text('Pay online / UPI')),
                    ],
                    child: const Chip(label: Text('Checkout')),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
