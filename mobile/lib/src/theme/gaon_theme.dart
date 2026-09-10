import 'package:flutter/material.dart';

abstract final class GaonPalette {
  static const green700 = Color(0xFF145B33);
  static const green600 = Color(0xFF1F7A45);
  static const green50 = Color(0xFFEAF4ED);
  static const neutral0 = Color(0xFFFFFFFF);
  static const neutral50 = Color(0xFFF6F8F4);
  static const neutral100 = Color(0xFFE8ECE7);
  static const neutral200 = Color(0xFFDFE7DF);
  static const neutral500 = Color(0xFF7C877F);
  static const neutral600 = Color(0xFF667069);
  static const neutral900 = Color(0xFF17221A);
  static const red700 = Color(0xFFB42318);
  static const red50 = Color(0xFFFFF0EE);
  static const amber700 = Color(0xFF765000);
  static const amber50 = Color(0xFFFFF8DB);
  static const blue700 = Color(0xFF3456A3);
  static const blue50 = Color(0xFFEEF4FF);
}

@immutable
class GaonColors extends ThemeExtension<GaonColors> {
  const GaonColors(
      {required this.surfaceSubtle,
      required this.surfaceDisabled,
      required this.textBrand,
      required this.textDisabled,
      required this.actionPressed,
      required this.actionSecondary,
      required this.borderSelected,
      required this.focusRing,
      required this.successBackground,
      required this.successText,
      required this.warningBackground,
      required this.warningText,
      required this.infoBackground,
      required this.infoText});
  final Color surfaceSubtle,
      surfaceDisabled,
      textBrand,
      textDisabled,
      actionPressed,
      actionSecondary,
      borderSelected,
      focusRing,
      successBackground,
      successText,
      warningBackground,
      warningText,
      infoBackground,
      infoText;
  static const standard = GaonColors(
      surfaceSubtle: GaonPalette.green50,
      surfaceDisabled: GaonPalette.neutral100,
      textBrand: GaonPalette.green700,
      textDisabled: GaonPalette.neutral600,
      actionPressed: GaonPalette.green700,
      actionSecondary: GaonPalette.green50,
      borderSelected: GaonPalette.green600,
      focusRing: GaonPalette.green700,
      successBackground: GaonPalette.green50,
      successText: GaonPalette.green700,
      warningBackground: GaonPalette.amber50,
      warningText: GaonPalette.amber700,
      infoBackground: GaonPalette.blue50,
      infoText: GaonPalette.blue700);
  @override
  GaonColors copyWith(
          {Color? surfaceSubtle,
          Color? surfaceDisabled,
          Color? textBrand,
          Color? textDisabled,
          Color? actionPressed,
          Color? actionSecondary,
          Color? borderSelected,
          Color? focusRing,
          Color? successBackground,
          Color? successText,
          Color? warningBackground,
          Color? warningText,
          Color? infoBackground,
          Color? infoText}) =>
      GaonColors(
          surfaceSubtle: surfaceSubtle ?? this.surfaceSubtle,
          surfaceDisabled: surfaceDisabled ?? this.surfaceDisabled,
          textBrand: textBrand ?? this.textBrand,
          textDisabled: textDisabled ?? this.textDisabled,
          actionPressed: actionPressed ?? this.actionPressed,
          actionSecondary: actionSecondary ?? this.actionSecondary,
          borderSelected: borderSelected ?? this.borderSelected,
          focusRing: focusRing ?? this.focusRing,
          successBackground: successBackground ?? this.successBackground,
          successText: successText ?? this.successText,
          warningBackground: warningBackground ?? this.warningBackground,
          warningText: warningText ?? this.warningText,
          infoBackground: infoBackground ?? this.infoBackground,
          infoText: infoText ?? this.infoText);
  @override
  GaonColors lerp(covariant GaonColors? other, double t) => other == null
      ? this
      : GaonColors(
          surfaceSubtle: Color.lerp(surfaceSubtle, other.surfaceSubtle, t)!,
          surfaceDisabled:
              Color.lerp(surfaceDisabled, other.surfaceDisabled, t)!,
          textBrand: Color.lerp(textBrand, other.textBrand, t)!,
          textDisabled: Color.lerp(textDisabled, other.textDisabled, t)!,
          actionPressed: Color.lerp(actionPressed, other.actionPressed, t)!,
          actionSecondary:
              Color.lerp(actionSecondary, other.actionSecondary, t)!,
          borderSelected: Color.lerp(borderSelected, other.borderSelected, t)!,
          focusRing: Color.lerp(focusRing, other.focusRing, t)!,
          successBackground:
              Color.lerp(successBackground, other.successBackground, t)!,
          successText: Color.lerp(successText, other.successText, t)!,
          warningBackground:
              Color.lerp(warningBackground, other.warningBackground, t)!,
          warningText: Color.lerp(warningText, other.warningText, t)!,
          infoBackground: Color.lerp(infoBackground, other.infoBackground, t)!,
          infoText: Color.lerp(infoText, other.infoText, t)!);
}

abstract final class GaonMetrics {
  static const spacing4 = 4.0,
      spacing8 = 8.0,
      spacing12 = 12.0,
      spacing16 = 16.0,
      spacing24 = 24.0,
      spacing32 = 32.0,
      spacing48 = 48.0;
  static const radius8 = 8.0, radius12 = 12.0, radius16 = 16.0, radius24 = 24.0;
  static const targetMin = 48.0, targetPrimary = 56.0;
  static const standardMotion = Duration(milliseconds: 150),
      reducedMotion = Duration.zero;
}

ThemeData gaonTheme() {
  const scheme = ColorScheme.light(
      primary: GaonPalette.green600,
      onPrimary: GaonPalette.neutral0,
      surface: GaonPalette.neutral0,
      onSurface: GaonPalette.neutral900,
      onSurfaceVariant: GaonPalette.neutral600,
      error: GaonPalette.red700,
      onError: GaonPalette.neutral0,
      errorContainer: GaonPalette.red50,
      onErrorContainer: GaonPalette.red700,
      outline: GaonPalette.neutral500,
      outlineVariant: GaonPalette.neutral200);
  const textTheme = TextTheme(
      bodyLarge: TextStyle(fontSize: 16, height: 24 / 16),
      bodyMedium: TextStyle(fontSize: 14, height: 20 / 14),
      labelLarge:
          TextStyle(fontSize: 16, height: 24 / 16, fontWeight: FontWeight.w600),
      titleMedium:
          TextStyle(fontSize: 20, height: 28 / 20, fontWeight: FontWeight.w600),
      titleLarge: TextStyle(
          fontSize: 24, height: 32 / 24, fontWeight: FontWeight.w600));
  return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      scaffoldBackgroundColor: GaonPalette.neutral50,
      textTheme: textTheme,
      extensions: const [GaonColors.standard],
      inputDecorationTheme:
          const InputDecorationTheme(border: OutlineInputBorder()),
      filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
              minimumSize: const Size(48, GaonMetrics.targetPrimary))),
      outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
              minimumSize: const Size(48, GaonMetrics.targetMin))));
}
