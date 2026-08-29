import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/customer_checkout_api.dart';
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
  bool checkoutBusy = false;
  String? error;
  String? selectedAddressId;
  String paymentMethod = 'cod';
  String? checkoutAttemptKey;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final results = await Future.wait([
        GaonApi.cart(),
        GaonApi.addresses(),
        GaonApi.villages(),
      ]);
      if (!mounted) return;
      final loadedAddresses = results[1] as List<AddressModel>;
      setState(() {
        cart = results[0] as CartModel;
        addresses = loadedAddresses;
        villages = results[2] as List<Village>;
        selectedAddressId ??= loadedAddresses.isEmpty ? null : loadedAddresses.first.id;
        if (selectedAddressId != null && !loadedAddresses.any((a) => a.id == selectedAddressId)) {
          selectedAddressId = loadedAddresses.isEmpty ? null : loadedAddresses.first.id;
        }
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

  void _resetCheckoutAttempt() {
    checkoutAttemptKey = null;
  }

  Future<void> setQuantity(CartItemModel item, int quantity) async {
    if (quantity < 1 || quantity > item.product.stock) return;
    try {
      final updated = await GaonApi.addToCart(item.product.id, quantity: quantity);
      if (!mounted) return;
      setState(() {
        cart = updated;
        _resetCheckoutAttempt();
      });
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<void> remove(String storeProductId) async {
    try {
      final updated = await GaonApi.removeCartItem(storeProductId);
      if (!mounted) return;
      setState(() {
        cart = updated;
        _resetCheckoutAttempt();
      });
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
                  items: villages
                      .map((v) => DropdownMenuItem(value: v.id, child: Text(v.name)))
                      .toList(),
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
        final created = await GaonApi.createAddress(
          villageId: villageId,
          label: label.text.trim(),
          landmark: landmark.text.trim(),
          houseDetails: house.text.trim(),
          directions: directions.text.trim(),
          latitude: position?.latitude,
          longitude: position?.longitude,
          isDefault: addresses.isEmpty,
        );
        _resetCheckoutAttempt();
        await load();
        if (mounted) setState(() => selectedAddressId = created.id);
      } catch (e) {
        _snack(e.toString());
      }
    }
  }

  Future<void> checkout() async {
    final currentCart = cart;
    final addressId = selectedAddressId;
    if (currentCart == null || currentCart.items.isEmpty || addressId == null || checkoutBusy) return;

    checkoutAttemptKey ??= 'mobile-${currentCart.id}-${DateTime.now().microsecondsSinceEpoch}';
    setState(() => checkoutBusy = true);
    try {
      final order = await CustomerCheckoutApi.checkout(
        addressId: addressId,
        paymentMethod: paymentMethod,
        idempotencyKey: checkoutAttemptKey!,
      );
      checkoutAttemptKey = null;
      if (!mounted) return;

      if (paymentMethod == 'upi') {
        final paid = await GaonApi.openRazorpayCheckout(order);
        if (!mounted) return;
        _snack(
          paid
              ? 'Order ${order.orderNumber} placed and payment confirmed.'
              : 'Order ${order.orderNumber} is placed. Payment is still pending and can be retried from Orders.',
        );
      } else {
        await showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Order placed'),
            content: Text(
              'Order ${order.orderNumber}\nTotal ₹${order.total}\nPayment: Cash on delivery',
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK')),
            ],
          ),
        );
      }
      await load();
    } catch (e) {
      // Keep the same idempotency key after transport/provider uncertainty so a
      // customer retry cannot create a duplicate order.
      _snack(e.toString());
    } finally {
      if (mounted) setState(() => checkoutBusy = false);
    }
  }

  void _snack(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(text.replaceFirst('Exception: ', ''))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    final c = cart;
    final selectedAddress = selectedAddressId == null
        ? null
        : addresses.where((a) => a.id == selectedAddressId).firstOrNull;

    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Your cart',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          if (c == null || c.items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(40),
              child: Center(child: Text('Your cart is empty.')),
            ),
          if (c != null)
            ...c.items.map(
              (item) => Card(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(item.product.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text('₹${item.product.price} • ${item.product.unit}'),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'Decrease quantity',
                        onPressed: item.quantity > 1 ? () => setQuantity(item, item.quantity - 1) : null,
                        icon: const Icon(Icons.remove_circle_outline),
                      ),
                      Text('${item.quantity}', style: const TextStyle(fontWeight: FontWeight.w800)),
                      IconButton(
                        tooltip: 'Increase quantity',
                        onPressed: item.quantity < item.product.stock
                            ? () => setQuantity(item, item.quantity + 1)
                            : null,
                        icon: const Icon(Icons.add_circle_outline),
                      ),
                      IconButton(
                        tooltip: 'Remove item',
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () => remove(item.product.id),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          if (c != null && c.items.isNotEmpty) ...[
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Delivery address',
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                          ),
                        ),
                        TextButton.icon(onPressed: addAddress, icon: const Icon(Icons.add), label: const Text('Add')),
                      ],
                    ),
                    if (addresses.isEmpty)
                      const Text('Add an address before checkout.')
                    else
                      DropdownButtonFormField<String>(
                        key: ValueKey(selectedAddressId),
                        initialValue: selectedAddressId,
                        decoration: const InputDecoration(labelText: 'Deliver to'),
                        items: addresses
                            .map(
                              (a) => DropdownMenuItem(
                                value: a.id,
                                child: Text('${a.label} • ${a.landmark}', overflow: TextOverflow.ellipsis),
                              ),
                            )
                            .toList(),
                        onChanged: (value) => setState(() {
                          selectedAddressId = value;
                          _resetCheckoutAttempt();
                        }),
                      ),
                    if (selectedAddress != null) ...[
                      const SizedBox(height: 8),
                      Text('${selectedAddress.houseDetails ?? ''} ${selectedAddress.landmark}'.trim()),
                      if (selectedAddress.latitude == null)
                        const Text('GPS not attached; serviceability will use village coverage.'),
                    ],
                    const SizedBox(height: 18),
                    Text(
                      'Payment',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    RadioGroup<String>(
                      groupValue: paymentMethod,
                      onChanged: (value) => setState(() {
                        paymentMethod = value ?? paymentMethod;
                        _resetCheckoutAttempt();
                      }),
                      child: const Column(
                        children: [
                          RadioListTile<String>(
                            contentPadding: EdgeInsets.zero,
                            value: 'cod',
                            title: Text('Cash on delivery'),
                            subtitle: Text('Pay after verified delivery'),
                          ),
                          RadioListTile<String>(
                            contentPadding: EdgeInsets.zero,
                            value: 'upi',
                            title: Text('UPI / online payment'),
                            subtitle: Text('Secure payment through Razorpay'),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      children: [
                        const Expanded(child: Text('Subtotal')),
                        Text('₹${c.subtotal}', style: const TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ),
                    const SizedBox(height: 6),
                    const Row(
                      children: [
                        Expanded(child: Text('Delivery fee')),
                        Text('Calculated at checkout'),
                      ],
                    ),
                    const SizedBox(height: 14),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: selectedAddressId == null || checkoutBusy ? null : checkout,
                        icon: checkoutBusy
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.lock_outline),
                        label: Text(checkoutBusy ? 'Placing order…' : 'Place order securely'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
