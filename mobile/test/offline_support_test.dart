import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/offline/offline_support.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    OfflineSupport.degraded.value = false;
  });

  test('falls back to the last successful snapshot when the network fails', () async {
    final live = await OfflineSupport.cached<int>(
      key: 'test-number',
      remote: () async => 42,
      encode: (value) => value,
      decode: (value) => value as int,
    );
    expect(live.data, 42);
    expect(live.fromCache, isFalse);

    final fallback = await OfflineSupport.cached<int>(
      key: 'test-number',
      remote: () async => throw Exception('offline'),
      encode: (value) => value,
      decode: (value) => value as int,
    );
    expect(fallback.data, 42);
    expect(fallback.fromCache, isTrue);
    expect(fallback.cachedAt, isNotNull);
    expect(OfflineSupport.degraded.value, isTrue);
  });
}
