import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

abstract class CheckoutGateway {
  Future<String> currentUserId();
  Future<CheckoutQuoteModel> quote(String addressId);
  Future<OrderModel> submit(PendingCheckoutAttempt attempt);
  Future<PendingCheckoutAttempt?> loadPending(String ownerUserId);
  Future<void> savePending(PendingCheckoutAttempt attempt);
  Future<void> clearPending(String ownerUserId);
  String newIdempotencyKey();
}

class GaonCheckoutGateway implements CheckoutGateway {
  @override Future<String> currentUserId() async => (await GaonApi.me()).id;
  @override Future<CheckoutQuoteModel> quote(String addressId) => GaonApi.cartQuote(addressId);
  @override Future<OrderModel> submit(PendingCheckoutAttempt attempt) => GaonApi.checkoutForOwner(attempt.addressId, attempt.paymentMethod, idempotencyKey: attempt.idempotencyKey,ownerUserId:attempt.ownerUserId);
  @override Future<PendingCheckoutAttempt?> loadPending(String ownerUserId) => GaonApi.pendingCheckout(ownerUserId);
  @override Future<void> savePending(PendingCheckoutAttempt attempt) => GaonApi.savePendingCheckout(attempt);
  @override Future<void> clearPending(String ownerUserId) => GaonApi.clearPendingCheckout(ownerUserId);
  @override String newIdempotencyKey() => GaonApi.newCheckoutIdempotencyKey();
}

class CheckoutBlockedException implements Exception {
  CheckoutBlockedException(this.message); final String message;
  @override String toString() => message;
}

class CheckoutResult {
  CheckoutResult(this.order, this.paymentMethod); final OrderModel order; final String paymentMethod;
}

class CheckoutAttemptCoordinator {
  CheckoutAttemptCoordinator(this.gateway); final CheckoutGateway gateway;
  PendingCheckoutAttempt? _pending; String? _loadedForUserId; bool busy = false;
  bool get hasUnresolvedAttempt => _pending != null;
  Future<String> _loadPending() async {final userId=await gateway.currentUserId();if(_loadedForUserId!=userId){_pending=await gateway.loadPending(userId);_loadedForUserId=userId;}return userId;}
  Future<bool> prepare() async {await _loadPending();return hasUnresolvedAttempt;}
  bool _isDefinitiveRejection(Object error) => error is ApiException && error is! SessionExpired && const {400,404,409}.contains(error.statusCode);
  Future<CheckoutResult> _submit(PendingCheckoutAttempt attempt) async {try {final order=await gateway.submit(attempt);await gateway.clearPending(attempt.ownerUserId);_pending=null;return CheckoutResult(order,attempt.paymentMethod);} catch(error){if(_isDefinitiveRejection(error)){await gateway.clearPending(attempt.ownerUserId);_pending=null;}rethrow;}}
  Future<CheckoutResult?> recover() async {if(busy)return null;busy=true;try{await _loadPending();if(_pending==null)return null;return await _submit(_pending!);}finally{busy=false;}}
  Future<CheckoutResult?> place({required String addressId,required String paymentMethod,required String cartFingerprint,required Future<bool> Function(CheckoutQuoteModel quote) confirm}) async {
    if(busy)return null;busy=true;
    try {final ownerUserId=await _loadPending();if(_pending!=null)return await _submit(_pending!);final quote=await gateway.quote(addressId);if(!quote.checkoutReady)throw CheckoutBlockedException(quote.blockers.isEmpty?'Checkout is not available for this address.':quote.blockers.join(' • '));if(!await confirm(quote))return null;if(await gateway.currentUserId()!=ownerUserId)throw const CheckoutSessionChanged();final attempt=PendingCheckoutAttempt(ownerUserId:ownerUserId,idempotencyKey:gateway.newIdempotencyKey(),addressId:addressId,paymentMethod:paymentMethod,cartFingerprint:cartFingerprint);await gateway.savePending(attempt);_pending=attempt;return await _submit(attempt);} finally {busy=false;}
  }
}

class CheckoutQuoteSummary extends StatelessWidget {
  const CheckoutQuoteSummary({super.key,required this.quote,required this.paymentMethod});final CheckoutQuoteModel quote;final String paymentMethod;
  Widget _row(String label,String amount,{bool strong=false})=>Padding(padding:const EdgeInsets.symmetric(vertical:4),child:Row(mainAxisAlignment:MainAxisAlignment.spaceBetween,children:[Text(label),Text('₹$amount',style:strong?const TextStyle(fontWeight:FontWeight.w800):null)]));
  @override Widget build(BuildContext context)=>Column(mainAxisSize:MainAxisSize.min,crossAxisAlignment:CrossAxisAlignment.stretch,children:[_row('Subtotal',quote.subtotal),_row('Local delivery',quote.deliveryFee),const Divider(),_row('Total',quote.total,strong:true),const SizedBox(height:12),Text(paymentMethod=='cod'?'Payment: Cash on delivery':'Payment: UPI / online'),const SizedBox(height:8),const Text('Stock, serviceability and prices are checked again when you place the order.')]);
}

class CartScreen extends StatefulWidget {
  const CartScreen({super.key,this.checkoutGateway,this.loadData});final CheckoutGateway? checkoutGateway;final Future<List<Object>> Function()? loadData;
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
  late final CheckoutAttemptCoordinator checkoutCoordinator;

  @override
  void initState() {
    super.initState();
    checkoutCoordinator = CheckoutAttemptCoordinator(widget.checkoutGateway??GaonCheckoutGateway());
    load();
  }

  Future<void> load() async {
    try {
      final results = await (widget.loadData?.call()??Future.wait<Object>([GaonApi.cart(), GaonApi.addresses(), GaonApi.villages()]));
      await checkoutCoordinator.prepare();
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
                  decoration: const InputDecoration(labelText: 'Area / locality'),
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
      if(checkoutCoordinator.busy)return;setState((){});final currentCart=cart;final result=await checkoutCoordinator.place(addressId:address.id,paymentMethod:payment,cartFingerprint:currentCart==null?'unknown':'${currentCart.id}|${currentCart.items.map((item)=>'${item.product.id}:${item.quantity}').join(',')}',confirm:(quote)=>_confirmQuote(quote,payment));if(result==null||!mounted)return;final order=result.order;final resolvedPayment=result.paymentMethod;
      await _completeCheckout(order,resolvedPayment);
    } catch (e) {
      _snack(checkoutCoordinator.hasUnresolvedAttempt?'The previous order result is not confirmed. Retry checkout to safely check the same order attempt.':e.toString());
    } finally {
      if(mounted)setState((){});
    }
  }

  Future<void> recoverCheckout() async {
    try {if(checkoutCoordinator.busy)return;setState((){});final result=await checkoutCoordinator.recover();if(result!=null&&mounted)await _completeCheckout(result.order,result.paymentMethod);}catch(e){_snack(checkoutCoordinator.hasUnresolvedAttempt?'The previous order result is still not confirmed. Try recovery again.':e.toString());}finally{if(mounted)setState((){});}
  }

  Future<void> _completeCheckout(OrderModel order,String resolvedPayment) async {
      if (!mounted) return;
      if (resolvedPayment == 'upi') {
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
  }

  Future<bool> _confirmQuote(CheckoutQuoteModel quote,String payment)async=>await showDialog<bool>(context:context,builder:(context)=>AlertDialog(title:const Text('Confirm order'),content:CheckoutQuoteSummary(quote:quote,paymentMethod:payment),actions:[TextButton(onPressed:()=>Navigator.pop(context,false),child:const Text('Cancel')),FilledButton(onPressed:()=>Navigator.pop(context,true),child:const Text('Place order'))]))??false;

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
          if(checkoutCoordinator.hasUnresolvedAttempt) Card(child:Padding(padding:const EdgeInsets.all(16),child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[const Text('An earlier order needs confirmation before another checkout.',style:TextStyle(fontWeight:FontWeight.w700)),const SizedBox(height:8),FilledButton(onPressed:checkoutCoordinator.busy?null:recoverCheckout,child:Text(checkoutCoordinator.busy?'Checking…':'Recover order'))]))),
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
                    enabled: !checkoutCoordinator.busy,
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
