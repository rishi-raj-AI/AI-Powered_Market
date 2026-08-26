import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gaonone_mobile/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('GaonOne opens the authentication experience', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const GaonOneApp());
    await tester.pumpAndSettle();

    expect(find.text('GaonOne'), findsWidgets);
  });
}
