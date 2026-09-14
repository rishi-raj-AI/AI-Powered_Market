import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/api/gaon_api.dart';
import 'package:gaonone_mobile/src/models/models.dart';
import 'package:gaonone_mobile/src/screens/cart_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

CheckoutQuoteModel checkoutQuote({bool ready = true}) => CheckoutQuoteModel.fromJson({
  'store_id': 'store-1',
  'address_id': 'address-1',
  'subtotal': '145.00',
  'delivery_fee': '37.50',
  'total': '182.50',
  'serviceable': ready,
  'inventory_valid': ready,
  'store_open': true,
  'checkout_ready': ready,
  'blockers': ready
      ? <String>[]
      : ['This store does not deliver to the selected address'],
});

OrderModel order(String id) => OrderModel(
  id: id,
  orderNumber: 'GO-$id',
  status: 'placed',
  paymentMethod: 'cod',
  paymentStatus: 'pending',
  total: '182.50',
  createdAt: '2026-09-14T00:00:00Z',
);

class FakeCheckoutGateway implements CheckoutGateway {
  String userId = 'user-a';
  CheckoutQuoteModel nextQuote = checkoutQuote();
  PendingCheckoutAttempt? stored;
  final List<PendingCheckoutAttempt> submissions = [];
  int quoteCalls = 0;
  int saved = 0;
  int cleared = 0;
  int keyNumber = 0;
  Completer<CheckoutQuoteModel>? quoteCompleter;
  Object? nextError;
  bool failSave = false;
  String? switchUserAfterSave;

  @override
  Future<String> currentUserId() async => userId;

  @override
  Future<CheckoutQuoteModel> quote(String addressId) {
    quoteCalls++;
    return quoteCompleter?.future ?? Future.value(nextQuote);
  }

  @override
  Future<OrderModel> submit(PendingCheckoutAttempt attempt) async {
    if(attempt.ownerUserId!=userId)throw const CheckoutSessionChanged();
    submissions.add(attempt);
    final error = nextError;
    nextError = null;
    if (error != null) throw error;
    return order('order-${submissions.length}');
  }

  @override
  Future<PendingCheckoutAttempt?> loadPending(String ownerUserId) async => stored?.ownerUserId==ownerUserId?stored:null;

  @override
  Future<void> savePending(PendingCheckoutAttempt attempt) async {
    if (failSave) throw StateError('storage unavailable');
    saved++;
    stored = attempt;
    if(switchUserAfterSave!=null)userId=switchUserAfterSave!;
  }

  @override
  Future<void> clearPending(String ownerUserId) async {
    cleared++;
    stored = null;
  }

  @override
  String newIdempotencyKey() => 'key-${++keyNumber}';
}

void main() {
  test('quote preserves server money, readiness and blockers', () {
    final ready = checkoutQuote();
    final blocked = checkoutQuote(ready: false);

    expect(ready.subtotal, '145.00');
    expect(ready.deliveryFee, '37.50');
    expect(ready.total, '182.50');
    expect(ready.checkoutReady, isTrue);
    expect(blocked.serviceable, isFalse);
    expect(blocked.inventoryValid, isFalse);
    expect(blocked.storeOpen, isTrue);
    expect(blocked.checkoutReady, isFalse);
    expect(blocked.blockers, [
      'This store does not deliver to the selected address',
    ]);
  });

  test('checkout header adapter preserves auth and adds the exact key', () {
    final headers = withIdempotencyKey({
      'Authorization': 'Bearer redacted',
    }, 'checkout-key');
    expect(headers, {
      'Authorization': 'Bearer redacted',
      'Idempotency-Key': 'checkout-key',
    });
  });

  test('quote request adapter sends the owned address as a query parameter', () {
    final uri = cartQuoteUri('https://example.test/api/v1', 'address-123');
    expect(uri.path, '/api/v1/cart/quote');
    expect(uri.queryParameters, {'address_id': 'address-123'});
  });

  testWidgets('quote summary displays only server-provided amounts', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CheckoutQuoteSummary(quote: checkoutQuote(), paymentMethod: 'cod'),
        ),
      ),
    );

    expect(find.text('₹145.00'), findsOneWidget);
    expect(find.text('₹37.50'), findsOneWidget);
    expect(find.text('₹182.50'), findsOneWidget);
    expect(find.textContaining('₹20'), findsNothing);
    expect(find.text('Payment: Cash on delivery'), findsOneWidget);
  });

  test('blocked quote and cancelled confirmation never submit', () async {
    final blockedGateway = FakeCheckoutGateway()
      ..nextQuote = checkoutQuote(ready: false);
    final blocked = CheckoutAttemptCoordinator(blockedGateway);
    await expectLater(
      blocked.place(
        addressId: 'address-1',
        paymentMethod: 'cod',
        cartFingerprint: 'cart-a',
        confirm: (_) async => true,
      ),
      throwsA(isA<CheckoutBlockedException>()),
    );
    expect(blockedGateway.submissions, isEmpty);
    expect(blockedGateway.saved, 0);

    final cancelledGateway = FakeCheckoutGateway();
    final cancelled = CheckoutAttemptCoordinator(cancelledGateway);
    expect(
      await cancelled.place(
        addressId: 'address-1',
        paymentMethod: 'cod',
        cartFingerprint: 'cart-a',
        confirm: (_) async => false,
      ),
      isNull,
    );
    expect(cancelledGateway.submissions, isEmpty);
    expect(cancelledGateway.saved, 0);
  });

  test('duplicate taps create one in-flight order mutation', () async {
    final gateway = FakeCheckoutGateway()
      ..quoteCompleter = Completer<CheckoutQuoteModel>();
    final coordinator = CheckoutAttemptCoordinator(gateway);
    final first = coordinator.place(
      addressId: 'address-1',
      paymentMethod: 'cod',
      cartFingerprint: 'cart-a',
      confirm: (_) async => true,
    );
    final duplicate = await coordinator.place(
      addressId: 'address-1',
      paymentMethod: 'cod',
      cartFingerprint: 'cart-a',
      confirm: (_) async => true,
    );
    expect(duplicate, isNull);
    gateway.quoteCompleter!.complete(checkoutQuote());
    expect((await first)?.order.id, 'order-1');
    expect(gateway.quoteCalls, 1);
    expect(gateway.submissions, hasLength(1));
  });

  test('lost response survives recreation and retries the original request and key', () async {
    final gateway = FakeCheckoutGateway()
      ..nextError = TimeoutException('response lost');
    final firstCoordinator = CheckoutAttemptCoordinator(gateway);
    await expectLater(
      firstCoordinator.place(
        addressId: 'address-original',
        paymentMethod: 'cod',
        cartFingerprint: 'cart-original',
        confirm: (_) async => true,
      ),
      throwsA(isA<TimeoutException>()),
    );
    expect(gateway.stored?.idempotencyKey, 'key-1');
    expect(gateway.stored?.ownerUserId, 'user-a');

    final recreated = CheckoutAttemptCoordinator(gateway);
    final recovered = await recreated.place(
      addressId: 'address-changed',
      paymentMethod: 'upi',
      cartFingerprint: 'cart-changed',
      confirm: (_) async => true,
    );
    expect(recovered?.paymentMethod, 'cod');
    expect(gateway.quoteCalls, 1);
    expect(gateway.submissions.map((item) => item.idempotencyKey), [
      'key-1',
      'key-1',
    ]);
    expect(gateway.submissions.last.addressId, 'address-original');
    expect(gateway.stored, isNull);
  });

  test('contract-defined rejection clears attempt and next logical order gets a new key', () async {
    final gateway = FakeCheckoutGateway()
      ..nextError = ApiException(
        'Cart inventory changed; review your cart',
        409,
      );
    final coordinator = CheckoutAttemptCoordinator(gateway);
    await expectLater(
      coordinator.place(
        addressId: 'address-1',
        paymentMethod: 'cod',
        cartFingerprint: 'cart-a',
        confirm: (_) async => true,
      ),
      throwsA(isA<ApiException>()),
    );
    expect(gateway.stored, isNull);

    final result = await coordinator.place(
      addressId: 'address-2',
      paymentMethod: 'upi',
      cartFingerprint: 'cart-b',
      confirm: (_) async => true,
    );
    expect(result?.paymentMethod, 'upi');
    expect(gateway.submissions.map((item) => item.idempotencyKey), [
      'key-1',
      'key-2',
    ]);
  });

  test('durable-storage failure fails closed before order submission', () async {
    final gateway = FakeCheckoutGateway()..failSave = true;
    final coordinator = CheckoutAttemptCoordinator(gateway);
    await expectLater(
      coordinator.place(addressId:'address-1',paymentMethod:'cod',cartFingerprint:'cart-a',confirm:(_)async=>true),
      throwsA(isA<StateError>()),
    );
    expect(gateway.submissions,isEmpty);
  });

  test('pending attempts are loaded for the current account only', () async {
    final storage=<String,PendingCheckoutAttempt>{};
    final userA=_AccountGateway(storage,'user-a');
    final first=CheckoutAttemptCoordinator(userA);
    userA.nextError=TimeoutException('lost');
    await expectLater(first.place(addressId:'address-a',paymentMethod:'cod',cartFingerprint:'cart-a',confirm:(_)async=>true),throwsA(isA<TimeoutException>()));
    final userB=_AccountGateway(storage,'user-b');
    final second=CheckoutAttemptCoordinator(userB);
    await second.place(addressId:'address-b',paymentMethod:'cod',cartFingerprint:'cart-b',confirm:(_)async=>true);
    expect(userB.submissions.single.addressId,'address-b');
    expect(storage['user-a']?.addressId,'address-a');
    final restored=CheckoutAttemptCoordinator(_AccountGateway(storage,'user-a'));
    expect((await restored.recover())?.order.id,'order-1');
  });

  test('one coordinator isolates A to B to A account changes',()async{
    final storage=<String,PendingCheckoutAttempt>{};
    final gateway=_AccountGateway(storage,'user-a')..nextError=TimeoutException('lost');
    final coordinator=CheckoutAttemptCoordinator(gateway);
    await expectLater(coordinator.place(addressId:'address-a',paymentMethod:'cod',cartFingerprint:'cart-a',confirm:(_)async=>true),throwsA(isA<TimeoutException>()));
    gateway.userId='user-b';
    expect((await coordinator.place(addressId:'address-b',paymentMethod:'cod',cartFingerprint:'cart-b',confirm:(_)async=>true))?.order.id,'order-2');
    gateway.userId='user-a';
    expect((await coordinator.recover())?.paymentMethod,'cod');
    expect(gateway.submissions.map((item)=>item.addressId),['address-a','address-b','address-a']);
  });

  test('account change during confirmation or before POST cannot submit as another user',()async{
    final duringConfirmation=FakeCheckoutGateway();
    final first=CheckoutAttemptCoordinator(duringConfirmation);
    await expectLater(first.place(addressId:'address-a',paymentMethod:'cod',cartFingerprint:'cart-a',confirm:(_)async{duringConfirmation.userId='user-b';return true;}),throwsA(isA<CheckoutSessionChanged>()));
    expect(duringConfirmation.submissions,isEmpty);
    expect(duringConfirmation.stored,isNull);

    final beforePost=FakeCheckoutGateway()..switchUserAfterSave='user-b';
    final second=CheckoutAttemptCoordinator(beforePost);
    await expectLater(second.place(addressId:'address-a',paymentMethod:'cod',cartFingerprint:'cart-a',confirm:(_)async=>true),throwsA(isA<CheckoutSessionChanged>()));
    expect(beforePost.submissions,isEmpty);
    expect(beforePost.stored?.ownerUserId,'user-a');
  });

  test('persistent pending checkout is account-scoped and malformed data blocks safely',()async{
    SharedPreferences.setMockInitialValues({});
    final attempt=PendingCheckoutAttempt(ownerUserId:'user-a',idempotencyKey:'key-a',addressId:'address-a',paymentMethod:'cod',cartFingerprint:'cart-a');
    await GaonApi.savePendingCheckout(attempt);
    expect((await GaonApi.pendingCheckout('user-a'))?.idempotencyKey,'key-a');
    expect(await GaonApi.pendingCheckout('user-b'),isNull);
    final prefs=await SharedPreferences.getInstance();
    await prefs.setString('pending_checkout_attempt_user-b','not-json');
    await expectLater(GaonApi.pendingCheckout('user-b'),throwsA(isA<StateError>()));
    expect((await GaonApi.pendingCheckout('user-a'))?.idempotencyKey,'key-a');
  });

  testWidgets('empty cart still exposes and runs pending-order recovery',(tester)async{
    final gateway=FakeCheckoutGateway()..stored=PendingCheckoutAttempt(ownerUserId:'user-a',idempotencyKey:'key-existing',addressId:'address-old',paymentMethod:'cod',cartFingerprint:'cart-old');
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:CartScreen(checkoutGateway:gateway,loadData:()async=><Object>[CartModel(id:'cart-empty',storeId:null,items:const[],subtotal:'0.00'),<AddressModel>[],<Village>[]]))));
    await tester.pumpAndSettle();
    expect(find.text('Your cart is empty.'),findsOneWidget);
    expect(find.text('Recover order'),findsOneWidget);
    await tester.tap(find.text('Recover order'));
    await tester.pumpAndSettle();
    expect(gateway.submissions.single.idempotencyKey,'key-existing');
    expect(gateway.quoteCalls,0);
  });
}

class _AccountGateway extends FakeCheckoutGateway {
  _AccountGateway(this.storage,String id){userId=id;}
  final Map<String,PendingCheckoutAttempt> storage;
  @override Future<PendingCheckoutAttempt?> loadPending(String ownerUserId)async=>storage[ownerUserId];
  @override Future<void> savePending(PendingCheckoutAttempt attempt)async{stored=attempt;storage[userId]=attempt;}
  @override Future<void> clearPending(String ownerUserId)async{stored=null;storage.remove(ownerUserId);}
}
