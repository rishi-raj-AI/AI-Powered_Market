import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

class GaonStrings {
  const GaonStrings(this.locale);
  final Locale locale;
  static const supportedLocales = [Locale('en'), Locale('hi'), Locale('mr')];
  static const LocalizationsDelegate<GaonStrings> delegate =
      _GaonStringsDelegate();
  static GaonStrings of(BuildContext context) =>
      Localizations.of<GaonStrings>(context, GaonStrings) ??
      const GaonStrings(Locale('en'));
  static const _messages = {
    'en': {
      'loading': 'Loading…',
      'retry': 'Try again',
      'subtotal': 'Subtotal',
      'deliveryFee': 'Local delivery',
      'total': 'Total'
    },
    'hi': {
      'loading': 'लोड हो रहा है…',
      'retry': 'फिर से कोशिश करें',
      'subtotal': 'उप-योग',
      'deliveryFee': 'स्थानीय डिलीवरी',
      'total': 'कुल'
    },
    'mr': {
      'loading': 'लोड होत आहे…',
      'retry': 'पुन्हा प्रयत्न करा',
      'subtotal': 'उपबेरीज',
      'deliveryFee': 'स्थानिक डिलिव्हरी',
      'total': 'एकूण'
    },
  };
  String text(String key) =>
      _messages[locale.languageCode]?[key] ?? _messages['en']![key] ?? key;
}

class _GaonStringsDelegate extends LocalizationsDelegate<GaonStrings> {
  const _GaonStringsDelegate();
  @override
  bool isSupported(Locale locale) => GaonStrings.supportedLocales
      .any((item) => item.languageCode == locale.languageCode);
  @override
  Future<GaonStrings> load(Locale locale) =>
      SynchronousFuture(GaonStrings(locale));
  @override
  bool shouldReload(covariant LocalizationsDelegate<GaonStrings> old) => false;
}
