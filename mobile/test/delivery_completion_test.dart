import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/screens/role_workspaces.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

http.Response _jsonResponse(Object body, [int statusCode = 200]) =>
    http.Response(
      jsonEncode(body),
      statusCode,
      headers: const {'content-type': 'application/json'},
    );

class _DeliveryHarness {
  _DeliveryHarness({
    this.paymentMethod = 'cod',
    this.completeReturnsUnavailable = false,
  });

  final String paymentMethod;
  final List<String> calls = [];
  bool completeReturnsUnavailable;
  String taskStatus = 'picked_up';
  int challengeRequests = 0;
  int myTaskReads = 0;
  int completeRequests = 0;
  Completer<http.Response>? pendingChallenge;
  Map<String, dynamic>? proofPayload;
  Map<String, dynamic>? collectionPayload;

  Map<String, dynamic> get task => {
        'id': 'delivery-1',
        'order_id': 'order-1',
        'order_number': 'GO2609030001',
        'status': taskStatus,
        'payment_method': paymentMethod,
        'payment_status': paymentMethod == 'cod' && taskStatus == 'delivered'
            ? 'paid'
            : 'pending',
        'total': '250.00',
        'store_name': 'Niphad Daily Needs',
        'store_landmark': 'Market Road',
        'recipient_name': 'Asha Patil',
        'recipient_phone': '+919876543210',
        'customer_landmark': 'Water tank',
      };

  Future<http.Response> handle(http.Request request) async {
    final path = request.url.path;
    calls.add('${request.method} $path');

    if (request.method == 'GET' && path.endsWith('/delivery/tasks/available')) {
      return _jsonResponse([]);
    }
    if (request.method == 'GET' && path.endsWith('/delivery/tasks/me')) {
      myTaskReads += 1;
      return _jsonResponse([task]);
    }
    if (request.method == 'POST' &&
        path.endsWith('/delivery-1/proof/challenge')) {
      challengeRequests += 1;
      final pending = pendingChallenge;
      if (pending != null) return pending.future;
      return _jsonResponse({
        'delivery_id': 'delivery-1',
        'expires_at': '2026-10-03T12:00:00Z',
      });
    }
    if (request.method == 'POST' && path.endsWith('/delivery-1/proof')) {
      proofPayload = Map<String, dynamic>.from(jsonDecode(request.body) as Map);
      return _jsonResponse({
        'id': 'proof-1',
        'delivery_id': 'delivery-1',
        'verified_at': '2026-10-03T11:00:00Z',
      });
    }
    if (request.method == 'POST' &&
        path.endsWith('/delivery-1/cod-collection')) {
      collectionPayload = Map<String, dynamic>.from(
        jsonDecode(request.body) as Map,
      );
      return _jsonResponse({
        'id': 'cod-1',
        'delivery_id': 'delivery-1',
        'order_id': 'order-1',
        'amount': '250.00',
      });
    }
    if (request.method == 'POST' && path.endsWith('/delivery-1/complete')) {
      completeRequests += 1;
      taskStatus = 'delivered';
      if (completeReturnsUnavailable)
        return _jsonResponse({'detail': 'Service unavailable'}, 503);
      return _jsonResponse({
        'id': 'delivery-1',
        'order_id': 'order-1',
        'status': 'delivered',
      });
    }
    return _jsonResponse({'detail': 'Unexpected request: $path'}, 404);
  }
}

Future<void> _pumpWorkspace(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(home: DeliveryWorkspace(onLogout: () {})),
  );
  await tester.pumpAndSettle();
}

Future<void> _sendCodeAndOpenCompletion(WidgetTester tester) async {
  await tester.tap(find.text('Send delivery code'));
  await tester.pumpAndSettle();
  final completionAction = find.text('Verify handoff & complete');
  final actionBox = tester.renderObject<RenderBox>(completionAction);
  final actionBottom =
      actionBox.localToGlobal(Offset(0, actionBox.size.height)).dy;
  final viewHeight = tester.binding.renderView.size.height;
  if (actionBottom > viewHeight) {
    await tester.drag(
      find.byType(ListView),
      Offset(0, viewHeight - actionBottom - 16),
    );
    await tester.pumpAndSettle();
  }
  await tester.tap(completionAction);
  await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField), '123456');
  await tester.pump();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
    'COD completion follows proof collection and completion endpoints',
    (tester) async {
      final harness = _DeliveryHarness();

      await http.runWithClient(() async {
        await _pumpWorkspace(tester);
        expect(find.text('Mark delivered'), findsNothing);

        await _sendCodeAndOpenCompletion(tester);
        await tester.tap(find.byType(CheckboxListTile));
        await tester.pump();
        await tester.tap(find.text('Confirm cash & complete'));
        await tester.pumpAndSettle();
      }, () => MockClient(harness.handle));

      expect(harness.proofPayload, {'otp': '123456'});
      expect(harness.collectionPayload, {'amount': '250.00'});
      expect(
        harness.calls,
        containsAllInOrder([
          'POST /api/v1/delivery/delivery-1/proof/challenge',
          'POST /api/v1/delivery/delivery-1/proof',
          'POST /api/v1/delivery/delivery-1/cod-collection',
          'POST /api/v1/delivery/delivery-1/complete',
        ]),
      );
      expect(
        harness.calls.where(
          (call) => call.startsWith('PATCH /api/v1/delivery/'),
        ),
        isEmpty,
      );
      expect(find.text('Verify handoff & complete'), findsNothing);
    },
  );

  testWidgets('prepaid completion does not record a COD collection', (
    tester,
  ) async {
    final harness = _DeliveryHarness(paymentMethod: 'upi');

    await http.runWithClient(() async {
      await _pumpWorkspace(tester);
      await _sendCodeAndOpenCompletion(tester);
      expect(find.byType(CheckboxListTile), findsNothing);
      await tester.tap(find.widgetWithText(FilledButton, 'Complete delivery'));
      await tester.pumpAndSettle();
    }, () => MockClient(harness.handle));

    expect(harness.proofPayload, {'otp': '123456'});
    expect(harness.collectionPayload, isNull);
    expect(
      harness.calls,
      contains('POST /api/v1/delivery/delivery-1/complete'),
    );
    expect(
      harness.calls.where((call) => call.contains('/cod-collection')),
      isEmpty,
    );
  });

  testWidgets('a pending proof-code request disables a duplicate mutation', (
    tester,
  ) async {
    final harness = _DeliveryHarness()
      ..pendingChallenge = Completer<http.Response>();

    await http.runWithClient(() async {
      await _pumpWorkspace(tester);
      await tester.tap(find.text('Send delivery code'));
      await tester.pump();

      expect(harness.challengeRequests, 1);
      expect(
        tester
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Sending delivery code…'),
            )
            .onPressed,
        isNull,
      );

      harness.pendingChallenge!.complete(
        _jsonResponse({
          'delivery_id': 'delivery-1',
          'expires_at': '2026-10-03T12:00:00Z',
        }),
      );
      await tester.pumpAndSettle();
    }, () => MockClient(harness.handle));

    expect(harness.challengeRequests, 1);
  });

  testWidgets(
    'an uncertain completion reloads server state instead of replaying it',
    (tester) async {
      final harness = _DeliveryHarness(completeReturnsUnavailable: true);

      await http.runWithClient(() async {
        await _pumpWorkspace(tester);
        await _sendCodeAndOpenCompletion(tester);
        await tester.tap(find.byType(CheckboxListTile));
        await tester.pump();
        await tester.tap(find.text('Confirm cash & complete'));
        await tester.pumpAndSettle();
      }, () => MockClient(harness.handle));

      expect(harness.completeRequests, 1);
      expect(harness.myTaskReads, greaterThanOrEqualTo(2));
      expect(find.text('Verify handoff & complete'), findsNothing);
      expect(
        harness.calls.where((call) => call.endsWith('/complete')),
        hasLength(1),
      );
    },
  );
}
