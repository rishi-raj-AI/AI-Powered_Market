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
  Map<String, dynamic>? health;
  Map<String, dynamic>? decision;
  List<AddressModel> addresses = [];
  List<Village> villages = [];
  bool loading = true;
  bool locating = false;
  bool checkoutBusy = false;
  bool decisionLoading = false;
  String? error;
  String? decisionError;
  String? selectedAddressId;
  String? checkoutAttemptKey;
  String paymentMethod = 'cod';

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result = await Future.wait([
        GaonApi.cart(),
        GaonApi.cartHealth(),
        GaonApi.addresses(),
        GaonApi.villages(),
      ]);
      if (!mounted) return;

      final nextAddresses = result[2] as List<AddressModel>;
      var nextSelected = selectedAddressId;
      if (nextSelected == null ||
          !nextAddresses.any((address) => address.id == nextSelected)) {
        nextSelected = nextAddresses.isEmpty ? null : nextAddresses.first.id;
      }

      setState(() {
        cart = result[0] as CartModel;
        health = result[1] as Map<String, dynamic>;
        addresses = nextAddresses;
        villages = result[3] as List<Village>;
        selectedAddressId = nextSelected;
        loading = false;
        error = null;
      });
      await _refreshDecision();
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString().replaceFirst('Exception: ', '');
        });
      }
    }
  }

  Future<void> _refreshDecision() async {
    final addressId = selectedAddressId;
    if (addressId == null) {
      if (mounted) {
        setState(() {
          decision = null;
          decisionError = null;
          decisionLoading = false;
        });
      }
      return;
    }

    if (mounted) {
      setState(() {
        decisionLoading = true;
        decisionError = null;
      });
    }
    try {
      final next = await GaonApi.checkoutDecision(addressId);
      if (mounted) {
        setState(() {
          decision = next;
          decisionLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          decision = null;
          decisionLoading = false;
          decisionError = e.toString().replaceFirst('Exception: ', '');
        });
      }
    }
  }

  void _resetCheckoutAttempt() {
    checkoutAttemptKey = null;
  }

  Future<void> setQuantity(CartItemModel item, int quantity) async {
    if (quantity < 1 || quantity > item.product.stock) return;
    try {
      await GaonApi.addToCart(item.product.id, quantity: quantity);
      _resetCheckoutAttempt();
      await load();
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<void> remove(String id) async {
    try {
      await GaonApi.removeCartItem(id);
      _resetCheckoutAttempt();
      await load();
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<Position?> _currentPosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      _snack(
        'Location services are switched off. You can still save the landmark manually.',
      );
      return null;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      _snack(
        'Location permission was not granted. Landmark-only address will still work.',
      );
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
                  decoration: const InputDecoration(
                    labelText: 'Service area fallback',
                    helperText: 'Use the landmark or GPS for the exact location.',
                  ),
                  items: villages
                      .map(
                        (v) => DropdownMenuItem(
                          value: v.id,
                          child: Text(v.name),
                        ),
                      )
                      .toList(),
                  onChanged: (value) =>
                      setLocal(() => villageId = value ?? villageId),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: label,
                  decoration: const InputDecoration(labelText: 'Label'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: house,
                  decoration: const InputDecoration(
                    labelText: 'House / area / locality',
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: landmark,
                  decoration: const InputDecoration(labelText: 'Landmark *'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: directions,
                  decoration: const InputDecoration(
                    labelText: 'Delivery directions',
                  ),
                ),
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
                  label: Text(
                    position == null
                        ? 'Attach current GPS location'
                        : 'GPS location attached',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Save'),
            ),
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
        selectedAddressId = created.id;
        await load();
      } catch (e) {
        _snack(e.toString());
      }
    }
  }

  Future<void> checkout() async {
    final currentCart = cart;
    final addressId = selectedAddressId;
    if (currentCart == null ||
        currentCart.items.isEmpty ||
        addressId == null ||
        checkoutBusy ||
        decisionLoading ||
        decision?['ready'] != true) {
      return;
    }

    checkoutAttemptKey ??=
        'mobile-${currentCart.id}-${DateTime.now().microsecondsSinceEpoch}';
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
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('OK'),
              ),
            ],
          ),
        );
      }
      await load();
    } catch (e) {
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

  String _humanize(dynamic value) =>
      value.toString().replaceAll('_', ' ').trim();

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());

    final currentCart = cart;
    final blocked = health?['status'] == 'blocked';
    final warning = health?['status'] == 'warning';
    final ready = decision?['ready'] == true;
    final blockers = (decision?['blockers'] as List?) ?? const [];
    final warnings = (decision?['warnings'] as List?) ?? const [];
    final selected = selectedAddressId == null
        ? null
        : addresses.where((a) => a.id == selectedAddressId).firstOrNull;

    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Your cart',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (currentCart != null && currentCart.items.isNotEmpty)
            Card(
              child: ListTile(
                leading: Icon(
                  blocked
                      ? Icons.error_outline
                      : warning
                          ? Icons.warning_amber_rounded
                          : Icons.verified_outlined,
                ),
                title: Text(
                  blocked
                      ? 'Cart needs attention'
                      : warning
                          ? 'Low stock warning'
                          : 'Cart inventory looks good',
                ),
                subtitle: Text(
                  blocked
                      ? 'Adjust unavailable quantities before checkout.'
                      : warning
                          ? 'Some items are running low.'
                          : 'Live inventory check passed.',
                ),
              ),
            ),
          if (currentCart != null &&
              currentCart.items.isNotEmpty &&
              selectedAddressId != null)
            Card(
              child: ListTile(
                leading: decisionLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(
                        ready
                            ? Icons.fact_check_outlined
                            : Icons.warning_amber_rounded,
                      ),
                title: Text(
                  decisionLoading
                      ? 'Rechecking checkout'
                      : ready
                          ? 'Ready for checkout'
                          : 'Checkout needs attention',
                ),
                subtitle: decisionError != null
                    ? Text('Could not verify checkout: $decisionError')
                    : ready
                        ? Text(
                            warnings.isEmpty
                                ? 'Stock, serviceability and checkout rules passed.'
                                : warnings.map(_humanize).join(' • '),
                          )
                        : Text(
                            blockers.isEmpty
                                ? 'Retry the checkout check before placing the order.'
                                : blockers.map(_humanize).join(' • '),
                          ),
                trailing: decisionError == null
                    ? null
                    : IconButton(
                        tooltip: 'Retry checkout check',
                        onPressed: _refreshDecision,
                        icon: const Icon(Icons.refresh),
                      ),
              ),
            ),
          if (currentCart == null || currentCart.items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(40),
              child: Center(child: Text('Your cart is empty.')),
            ),
          if (currentCart != null)
            ...currentCart.items.map(
              (item) => Card(
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.product.name,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w700),
                            ),
                            Text('₹${item.product.price} • ${item.product.unit}'),
                            Text(
                              '${item.product.stock} in stock',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'Decrease quantity',
                        onPressed: item.quantity > 1
                            ? () => setQuantity(item, item.quantity - 1)
                            : null,
                        icon: const Icon(Icons.remove_circle_outline),
                      ),
                      Text(
                        '${item.quantity}',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      IconButton(
                        tooltip: 'Increase quantity',
                        onPressed: item.quantity < item.product.stock
                            ? () => setQuantity(item, item.quantity + 1)
                            : null,
                        icon: const Icon(Icons.add_circle_outline),
                      ),
                      IconButton(
                        tooltip: 'Remove item',
                        onPressed: () => remove(item.product.id),
                        icon: const Icon(Icons.delete_outline),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          if (currentCart != null && currentCart.items.isNotEmpty) ...[
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
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                        ),
                        TextButton.icon(
                          onPressed: addAddress,
                          icon: const Icon(Icons.add),
                          label: const Text('Add'),
                        ),
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
                              (address) => DropdownMenuItem(
                                value: address.id,
                                child: Text(
                                  '${address.label} • ${address.landmark}',
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: (value) async {
                          setState(() => selectedAddressId = value);
                          _resetCheckoutAttempt();
                          await _refreshDecision();
                        },
                      ),
                    if (selected != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        '${selected.houseDetails ?? ''} ${selected.landmark}'
                            .trim(),
                      ),
                      if (selected.directions?.isNotEmpty == true)
                        Text(
                          selected.directions!,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                    const SizedBox(height: 18),
                    Text(
                      'Payment',
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
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
                        Text(
                          '₹${decision?['subtotal'] ?? currentCart.subtotal}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                    if (decision?['delivery_fee'] != null)
                      Row(
                        children: [
                          const Expanded(child: Text('Delivery')),
                          Text('₹${decision!['delivery_fee']}'),
                        ],
                      ),
                    if (decision?['total'] != null)
                      Row(
                        children: [
                          const Expanded(child: Text('Total')),
                          Text(
                            '₹${decision!['total']}',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ],
                      ),
                    if (decision?['merchant_reliability'] != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          'Store fulfilment signal ${(100 * (decision!['merchant_reliability'] as num)).round()}% • ${decision?['merchant_reliability_samples'] ?? 0} sampled orders',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    const SizedBox(height: 14),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: selectedAddressId == null ||
                                checkoutBusy ||
                                blocked ||
                                decisionLoading ||
                                !ready
                            ? null
                            : checkout,
                        icon: checkoutBusy
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.lock_outline),
                        label: Text(
                          decisionLoading
                              ? 'Rechecking checkout…'
                              : !ready
                                  ? 'Resolve checkout blockers'
                                  : checkoutBusy
                                      ? 'Placing order…'
                                      : 'Place order securely',
                        ),
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
