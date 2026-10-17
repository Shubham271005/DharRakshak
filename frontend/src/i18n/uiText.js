// UI labels in every supported language.
//
// Rule: never type farmer-facing English directly in a screen. Add a key
// here with BOTH "en" and "hi", then use `t('your_key')` from useLanguage().
// Component 8 moves this into shared/i18n/*.json — screens won't change.
export const UI_TEXT = {
  app_name: { en: 'DharRakshak', hi: 'धररक्षक' },
  app_tagline: {
    en: 'From crop symptoms to smarter farming decisions',
    hi: 'फसल के लक्षणों से बेहतर खेती के फैसलों तक',
  },
  language: { en: 'Language', hi: 'भाषा' },

  nav_profile: { en: 'My crop', hi: 'मेरी फसल' },
  nav_analysis: { en: 'Leaf check', hi: 'पत्ती जाँच' },
  nav_finance: { en: 'Loans & documents', hi: 'लोन और कागज़ात' },
  nav_chat: { en: 'Ask DharRakshak', hi: 'धररक्षक से पूछें' },

  mock_mode: { en: 'Demo mode · sample data', hi: 'डेमो मोड · नमूना डेटा' },
  server_ok: { en: 'Connected to server', hi: 'सर्वर से जुड़ा है' },
  server_down: { en: 'Server not reachable', hi: 'सर्वर से संपर्क नहीं' },
  mock_data: { en: 'MOCK DATA', hi: 'नमूना डेटा' },
  demo_example: { en: 'DEMO EXAMPLE', hi: 'डेमो उदाहरण' },
  estimate: { en: 'estimate', hi: 'अनुमान' },

  loading: { en: 'Loading…', hi: 'लोड हो रहा है…' },
  error_title: { en: 'Something went wrong', hi: 'कुछ गड़बड़ हो गई' },
  retry: { en: 'Try again', hi: 'फिर से कोशिश करें' },
  screen_crashed: {
    en: 'This screen hit an error. Other screens still work.',
    hi: 'इस स्क्रीन में त्रुटि आई। बाकी स्क्रीन काम कर रही हैं।',
  },
  under_construction: {
    en: 'This screen is being built by',
    hi: 'यह स्क्रीन बना रहे हैं',
  },
  raw_data: { en: 'Data this screen receives', hi: 'इस स्क्रीन को मिलने वाला डेटा' },
}
