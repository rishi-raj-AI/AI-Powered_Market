import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/models/models.dart';
import 'package:gaonone_mobile/src/widgets/address_pin_repair_action.dart';
import 'package:gaonone_mobile/src/widgets/delivery_pin_picker.dart';

AddressModel address(String id) => AddressModel(
      id: id,
      villageId: 'village-1',
      label: 'Home',
      landmark: 'Near school',
    );

const selectedPin = DeliveryPinCandidate(
  latitude: 18.5204,
  longitude: 73.8567,
  source: 'map_pin',
);

void main() {
  testWidgets('cancelled pin selection never calls replacement endpoint',
      (tester) async {
    var writes = 0;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AddressPinRepairAction(
          address: address('old-address'),
          selectPin: (_) async => null,
          confirmPin: (_, __) async {
            writes++;
            return address('new-address');
          },
          onReplaced: (_) async {},
        ),
      ),
    ));
    await tester.tap(find.text('Confirm saved address pin'));
    await tester.pumpAndSettle();
    expect(writes, 0);
  });

  testWidgets('confirmed pin uses old ID and refreshes with new address ID',
      (tester) async {
    String? submittedId;
    DeliveryPinCandidate? submittedPin;
    String? refreshedId;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AddressPinRepairAction(
          address: address('old-address'),
          selectPin: (_) async => selectedPin,
          confirmPin: (id, pin) async {
            submittedId = id;
            submittedPin = pin;
            return address('replacement-address');
          },
          onReplaced: (replacement) async {
            refreshedId = replacement.id;
          },
        ),
      ),
    ));
    expect(submittedId, isNull);
    await tester.tap(find.text('Confirm saved address pin'));
    await tester.pumpAndSettle();
    expect(submittedId, 'old-address');
    expect(submittedPin?.latitude, 18.5204);
    expect(submittedPin?.source, 'map_pin');
    expect(refreshedId, 'replacement-address');
    expect(find.textContaining('Delivery pin saved.'), findsOneWidget);
  });

  testWidgets('backend rejection preserves old address and shows error',
      (tester) async {
    var refreshed = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AddressPinRepairAction(
          address: address('old-address'),
          selectPin: (_) async => selectedPin,
          confirmPin: (_, __) async => throw Exception('out of zone'),
          onReplaced: (_) async { refreshed = true; },
        ),
      ),
    ));
    await tester.tap(find.text('Confirm saved address pin'));
    await tester.pumpAndSettle();
    expect(refreshed, isFalse);
    expect(find.textContaining('Your existing address is unchanged.'),
        findsOneWidget);
  });

  testWidgets('invalid candidate cannot be submitted', (tester) async {
    var writes = 0;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AddressPinRepairAction(
          address: address('old-address'),
          selectPin: (_) async => const DeliveryPinCandidate(
            latitude: 200,
            longitude: 73.8567,
            source: 'map_pin',
          ),
          confirmPin: (_, __) async {
            writes++;
            return address('new-address');
          },
          onReplaced: (_) async {},
        ),
      ),
    ));
    await tester.tap(find.text('Confirm saved address pin'));
    await tester.pumpAndSettle();
    expect(writes, 0);
    expect(find.textContaining('Your existing address is unchanged.'),
        findsOneWidget);
  });
}
