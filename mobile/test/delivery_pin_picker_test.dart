import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/widgets/delivery_pin_picker.dart';

void main() {
  test('a map centre is never treated as a customer-confirmed pin', () {
    const initial = DeliveryPinCandidate(
      latitude: 20.0778,
      longitude: 73.7898,
      source: 'map_pin',
    );
    expect(initial.isValid, isTrue);
    expect(
      const DeliveryPinCandidate(
        latitude: 200,
        longitude: 73.7898,
        source: 'gps',
      ).isValid,
      isFalse,
    );
    expect(
      const DeliveryPinCandidate(
        latitude: 20.0778,
        longitude: 73.7898,
        source: 'gps',
        accuracyMeters: -1,
      ).isValid,
      isFalse,
    );
  });

  testWidgets('opening the picker does not select or confirm its default centre',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: DeliveryPinPicker(showTiles: false),
    ));
    await tester.pump();
    expect(find.text('No pin selected. Tap the map or use GPS.'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Confirm delivery pin'),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('GPS pin requires a second explicit confirmation',
      (tester) async {
    DeliveryPinCandidate? saved;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: FilledButton(
            onPressed: () async {
              saved = await Navigator.of(context).push<DeliveryPinCandidate>(
                MaterialPageRoute(
                  builder: (_) => DeliveryPinPicker(
                    showTiles: false,
                    locate: () async => const DeliveryPinCandidate(
                      latitude: 18.5204,
                      longitude: 73.8567,
                      source: 'gps',
                      accuracyMeters: 18,
                    ),
                  ),
                ),
              );
            },
            child: const Text('Open pin picker'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('Open pin picker'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Use my current location'));
    await tester.pumpAndSettle();
    expect(saved, isNull, reason: 'GPS alone must never save an address pin');
    expect(find.text('Reported GPS accuracy: ±18 m'), findsOneWidget);
    await tester.tap(find.text('Confirm delivery pin'));
    await tester.pumpAndSettle();
    expect(saved?.latitude, 18.5204);
    expect(saved?.longitude, 73.8567);
    expect(saved?.source, 'gps');
  });

  testWidgets('GPS timeout retains manual selection and no automatic pin',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: DeliveryPinPicker(
        showTiles: false,
        locate: () async => throw TimeoutException('GPS unavailable'),
      ),
    ));
    await tester.pump();
    await tester.tap(find.text('Use my current location'));
    await tester.pumpAndSettle();
    expect(find.text('GPS timed out. Retry or tap the map manually.'),
        findsOneWidget);
    expect(
      tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Confirm delivery pin'),
      ).onPressed,
      isNull,
    );
  });
}
