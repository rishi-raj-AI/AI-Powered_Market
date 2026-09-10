import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/localization/gaon_strings.dart';
import 'package:gaonone_mobile/src/theme/gaon_theme.dart';

void main() {
  test('Material 3 theme maps GaonOne semantic roles', () {
    final theme = gaonTheme();
    expect(theme.useMaterial3, isTrue);
    expect(theme.colorScheme.primary, GaonPalette.green600);
    expect(theme.colorScheme.onSurface, GaonPalette.neutral900);
    expect(theme.extension<GaonColors>()?.warningText, GaonPalette.amber700);
  });

  test('foundation strings support English Hindi and Marathi', () {
    expect(GaonStrings.supportedLocales.map((locale) => locale.languageCode),
        ['en', 'hi', 'mr']);
    expect(const GaonStrings(Locale('hi')).text('total'), 'कुल');
    expect(const GaonStrings(Locale('mr')).text('total'), 'एकूण');
  });
}
