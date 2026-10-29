import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/api/gaon_api.dart';

void main() {
  test('QA build targets the approved HTTPS API with legacy OTP disabled', () {
    if (!const bool.fromEnvironment('GAONONE_QA_BUILD')) return;
    expect(GaonApi.baseUrl, 'https://gaonone.in/api/v1');
    expect(const bool.fromEnvironment('GAONONE_LEGACY_OTP_ENABLED'), isFalse);
  });
}
