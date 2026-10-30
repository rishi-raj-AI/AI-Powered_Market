import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart' as google;
import 'package:google_maps_flutter_platform_interface/google_maps_flutter_platform_interface.dart';
import 'package:gaonone_mobile/src/widgets/delivery_map.dart';

class MapStub extends GoogleMapsFlutterPlatform {
  @override
  Widget buildViewWithConfiguration(
          int creationId, PlatformViewCreatedCallback onCreated,
          {required MapWidgetConfiguration widgetConfiguration,
          MapObjects mapObjects = const MapObjects(),
          MapConfiguration mapConfiguration = const MapConfiguration()}) =>
      const Text('Native map stub');
}

void main() {
  testWidgets(
      'Google opt-in preserves explicit fallback without requesting GPS',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final original = GoogleMapsFlutterPlatform.instance;
    GoogleMapsFlutterPlatform.instance = MapStub();
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
      GoogleMapsFlutterPlatform.instance = original;
    });
    await tester.pumpWidget(const MaterialApp(
        home: SizedBox(
            height: 240,
            child: DeliveryMap(
              center: google.LatLng(20, 73),
              markers: {},
              fallback: Text('Existing alternative map'),
            ))));
    if (DeliveryMap.googleEnabled) {
      final map =
          tester.widget<google.GoogleMap>(find.byType(google.GoogleMap));
      expect(map.myLocationEnabled, isFalse);
      expect(map.trafficEnabled, isFalse);
      await tester.tap(find.text('Use alternative map'));
      await tester.pump();
    }
    expect(find.text('Existing alternative map'), findsOneWidget);
    expect(find.byType(google.GoogleMap), findsNothing);
    debugDefaultTargetPlatformOverride = null;
  });

  test('iOS keeps the existing map even when Android configuration is supplied',
      () {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    addTearDown(() => debugDefaultTargetPlatformOverride = null);
    expect(DeliveryMap.googleEnabled, isFalse);
  });
}
