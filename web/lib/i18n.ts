export const supportedLocales = ['en', 'hi', 'mr'] as const;
export type GaonLocale = (typeof supportedLocales)[number];
const messages = {
  en: {'common.loading': 'Loading…', 'common.retry': 'Try again', 'checkout.subtotal': 'Subtotal', 'checkout.deliveryFee': 'Local delivery', 'checkout.total': 'Total'},
  hi: {'common.loading': 'लोड हो रहा है…', 'common.retry': 'फिर से कोशिश करें', 'checkout.subtotal': 'उप-योग', 'checkout.deliveryFee': 'स्थानीय डिलीवरी', 'checkout.total': 'कुल'},
  mr: {'common.loading': 'लोड होत आहे…', 'common.retry': 'पुन्हा प्रयत्न करा', 'checkout.subtotal': 'उपबेरीज', 'checkout.deliveryFee': 'स्थानिक डिलिव्हरी', 'checkout.total': 'एकूण'},
} as const;
export type MessageKey = keyof typeof messages.en;
export function normalizeLocale(value?: string | null): GaonLocale { const language = value?.toLowerCase().split('-')[0]; return supportedLocales.includes(language as GaonLocale) ? language as GaonLocale : 'en'; }
export function translate(locale: GaonLocale, key: MessageKey): string { return messages[locale][key]; }
