import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/src/theme/gaon_theme.dart';

void main() {
  test('Material 3 theme maps GaonOne semantic roles explicitly', () {
    final theme = gaonTheme();

    expect(theme.useMaterial3, isTrue);
    expect(theme.colorScheme.primary, GaonPalette.green600);
    expect(theme.colorScheme.onPrimary, GaonPalette.neutral0);
    expect(theme.colorScheme.primaryContainer, GaonPalette.green50);
    expect(theme.colorScheme.onPrimaryContainer, GaonPalette.green700);
    expect(theme.colorScheme.secondary, GaonPalette.green700);
    expect(theme.colorScheme.onSecondary, GaonPalette.neutral0);
    expect(theme.colorScheme.secondaryContainer, GaonPalette.green50);
    expect(theme.colorScheme.onSecondaryContainer, GaonPalette.green700);
    expect(theme.colorScheme.tertiary, GaonPalette.blue700);
    expect(theme.colorScheme.onTertiary, GaonPalette.neutral0);
    expect(theme.colorScheme.tertiaryContainer, GaonPalette.blue50);
    expect(theme.colorScheme.onTertiaryContainer, GaonPalette.blue700);
    expect(theme.colorScheme.surface, GaonPalette.neutral0);
    expect(theme.colorScheme.onSurface, GaonPalette.neutral900);
    expect(theme.colorScheme.onSurfaceVariant, GaonPalette.neutral600);
    expect(theme.colorScheme.error, GaonPalette.red700);
    expect(theme.colorScheme.outline, GaonPalette.neutral500);
    expect(theme.scaffoldBackgroundColor, GaonPalette.neutral50);
    expect(theme.inputDecorationTheme.border, isA<OutlineInputBorder>());
    expect(theme.extension<GaonColors>()?.warningText, GaonPalette.amber700);
  });

  testWidgets('tonal actions and customer navigation use explicit brand roles',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: gaonTheme(),
      home: Scaffold(
        body: FilledButton.tonal(
          key: const Key('tonal-action'),
          onPressed: () {},
          child: const Text('Use my current location'),
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: 0,
          destinations: const [
            NavigationDestination(
                icon: Icon(Icons.storefront), label: 'Market'),
            NavigationDestination(
                icon: Icon(Icons.shopping_cart), label: 'Cart'),
          ],
        ),
      ),
    ));

    final tonal =
        tester.widget<FilledButton>(find.byKey(const Key('tonal-action')));
    final tonalDefaults = tonal.defaultStyleOf(
      tester.element(find.byKey(const Key('tonal-action'))),
    );
    expect(
      tonalDefaults.backgroundColor?.resolve(<WidgetState>{}),
      GaonPalette.green50,
    );
    expect(
      tonalDefaults.foregroundColor?.resolve(<WidgetState>{}),
      GaonPalette.green700,
    );
    expect(
      tester
          .widget<NavigationIndicator>(find.byType(NavigationIndicator).first)
          .color,
      GaonPalette.green50,
    );
  });

  testWidgets('enabled and disabled controls retain minimum touch targets', (
    tester,
  ) async {
    final controls = <Widget>[
      FilledButton(
        key: const Key('filled-enabled'),
        onPressed: () {},
        child: const Text('Continue'),
      ),
      const FilledButton(
        key: Key('filled-disabled'),
        onPressed: null,
        child: Text('Continue'),
      ),
      OutlinedButton(
        key: const Key('outlined-enabled'),
        onPressed: () {},
        child: const Text('Back'),
      ),
      const OutlinedButton(
        key: Key('outlined-disabled'),
        onPressed: null,
        child: Text('Back'),
      ),
      TextButton(
        key: const Key('text-enabled'),
        onPressed: () {},
        child: const Text('Cancel'),
      ),
      const TextButton(
        key: Key('text-disabled'),
        onPressed: null,
        child: Text('Cancel'),
      ),
      IconButton(
        key: const Key('icon-enabled'),
        onPressed: () {},
        icon: const Icon(Icons.close),
        tooltip: 'Close',
      ),
      const IconButton(
        key: Key('icon-disabled'),
        onPressed: null,
        icon: Icon(Icons.close),
        tooltip: 'Close unavailable',
      ),
    ];
    await tester.pumpWidget(
      MaterialApp(
        theme: gaonTheme(),
        home: Scaffold(
          body: SingleChildScrollView(child: Column(children: controls)),
        ),
      ),
    );

    for (final key in ['filled-enabled', 'filled-disabled']) {
      final size = tester.getSize(find.byKey(Key(key)));
      expect(size.width, greaterThanOrEqualTo(GaonMetrics.targetMin));
      expect(size.height, greaterThanOrEqualTo(GaonMetrics.targetPrimary));
    }
    for (final key in [
      'outlined-enabled',
      'outlined-disabled',
      'text-enabled',
      'text-disabled',
      'icon-enabled',
      'icon-disabled',
    ]) {
      final size = tester.getSize(find.byKey(Key(key)));
      expect(size.width, greaterThanOrEqualTo(GaonMetrics.targetMin));
      expect(size.height, greaterThanOrEqualTo(GaonMetrics.targetMin));
    }
  });

  testWidgets(
    'narrow English Hindi and Marathi labels respect system 2x text scaling',
    (tester) async {
      const scaler = TextScaler.linear(2);
      const labels = [
        'Check delivery availability for this address and continue',
        'इस पते पर डिलीवरी की उपलब्धता जाँचें और आगे बढ़ें',
        'या पत्त्यावर वितरण उपलब्ध आहे का ते तपासा आणि पुढे जा',
      ];
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(size: Size(320, 900), textScaler: scaler),
          child: Theme(
            data: gaonTheme(),
            child: Directionality(
              textDirection: TextDirection.ltr,
              child: Align(
                alignment: Alignment.topCenter,
                child: SizedBox(
                  width: 320,
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        for (var index = 0; index < labels.length; index++)
                          Padding(
                            padding: const EdgeInsets.all(8),
                            child: FilledButton(
                              key: Key('localized-$index'),
                              onPressed: () {},
                              child: Text(labels[index]),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );

      expect(
        MediaQuery.textScalerOf(
          tester.element(find.byKey(const Key('localized-0'))),
        ),
        scaler,
      );
      for (var index = 0; index < labels.length; index++) {
        final size = tester.getSize(find.byKey(Key('localized-$index')));
        expect(size.width, lessThanOrEqualTo(304));
        expect(size.height, greaterThanOrEqualTo(GaonMetrics.targetPrimary));
      }
      expect(tester.takeException(), isNull);
    },
  );
}
