/**
 * I18n Manager for PyPRLedger
 * Supports: en, zh-CN, zh-TW
 * Auto-detects browser language and allows manual switching
 */

class I18nManager {
  constructor() {
    this.translations = {};
    this.currentLocale = this.getStoredLocale() || this.detectBrowserLanguage();
    this.fallbackLocale = 'en';
    this.supportedLocales = ['en', 'zh-CN', 'zh-TW'];
  }

  /**
   * Detect browser language and map to supported locales
   * Priority: zh-TW > zh-CN > en
   */
  detectBrowserLanguage() {
    const browserLang = navigator.language || navigator.userLanguage || 'en';
    
    // Check for Traditional Chinese
    if (browserLang.includes('TW') || browserLang.includes('HK') || browserLang === 'zh-Hant') {
      return 'zh-TW';
    }
    
    // Check for Simplified Chinese
    if (browserLang.startsWith('zh') || browserLang === 'zh-Hans') {
      return 'zh-CN';
    }
    
    // Default to English
    return 'en';
  }

  /**
   * Get stored locale preference from localStorage
   */
  getStoredLocale() {
    try {
      const stored = localStorage.getItem('locale');
      // Ensure stored value is a string before checking
      if (stored && typeof stored === 'string' && this.supportedLocales.includes(stored)) {
        return stored;
      }
    } catch (e) {
      console.warn('Failed to read locale from localStorage:', e);
    }
    return null;
  }

  /**
   * Store locale preference to localStorage
   */
  storeLocale(locale) {
    try {
      localStorage.setItem('locale', locale);
    } catch (e) {
      console.warn('Failed to store locale to localStorage:', e);
    }
  }

  /**
   * Initialize i18n system
   * Loads translations and applies language to the page
   */
  async init() {
    try {
      // Load fallback locale first
      await this.loadTranslations(this.fallbackLocale);
      
      // Load current locale if different from fallback
      if (this.currentLocale !== this.fallbackLocale) {
        await this.loadTranslations(this.currentLocale);
      }
      
      // Apply language to the page
      this.applyLanguage();
      
      console.log(`[I18n] Initialized with locale: ${this.currentLocale}`);
    } catch (error) {
      console.error('[I18n] Failed to initialize:', error);
    }
  }

  /**
   * Load translations for a specific locale
   */
  async loadTranslations(locale) {
    if (this.translations[locale]) {
      return; // Already loaded
    }

    try {
      const response = await fetch(`/web/i18n/locales/${locale}.json`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      this.translations[locale] = await response.json();
      console.log(`[I18n] Loaded translations for: ${locale}`);
    } catch (error) {
      console.error(`[I18n] Failed to load translations for ${locale}:`, error);
      // Use empty object as fallback to prevent crashes
      this.translations[locale] = {};
    }
  }

  /**
   * Translate a key to the current locale
   * Supports nested keys like "app.title" and parameter replacement
   * 
   * @param {string} key - Translation key (dot-separated)
   * @param {object} params - Optional parameters for replacement
   * @returns {string} Translated text
   */
  t(key, params = {}) {
    const keys = key.split('.');
    
    // Try current locale first
    let value = this.getNestedValue(this.translations[this.currentLocale], keys);
    
    // Fallback to English if translation not found
    if (!value && this.currentLocale !== this.fallbackLocale) {
      value = this.getNestedValue(this.translations[this.fallbackLocale], keys);
    }
    
    // If still not found, return the key itself
    if (!value) {
      console.warn(`[I18n] Missing translation for key: ${key}`);
      return key;
    }

    // Replace parameters {{param}} with actual values
    if (typeof value === 'string' && Object.keys(params).length > 0) {
      return value.replace(/\{\{(\w+)\}\}/g, (_, param) => {
        return params[param] !== undefined ? params[param] : `{{${param}}}`;
      });
    }

    return value;
  }

  /**
   * Get nested value from object using array of keys
   */
  getNestedValue(obj, keys) {
    if (!obj || !keys || keys.length === 0) {
      return undefined;
    }
    
    let value = obj;
    for (const key of keys) {
      if (value === undefined || value === null) {
        return undefined;
      }
      value = value[key];
    }
    
    return value;
  }

  /**
   * Change the current locale without reloading the page
   */
  setLocale(locale) {
    // Ensure locale is a string
    if (typeof locale !== 'string') {
      console.warn(`[I18n] Invalid locale type: ${typeof locale}`);
      return;
    }
    
    if (!this.supportedLocales.includes(locale)) {
      console.warn(`[I18n] Unsupported locale: ${locale}`);
      return;
    }

    if (locale === this.currentLocale) {
      return; // No change needed
    }

    this.currentLocale = locale;
    this.storeLocale(locale);
    
    // Load translations for the new locale if not already loaded
    this.loadTranslations(locale).then(() => {
      // Apply language to the page without reload
      this.applyLanguage();
      console.log(`[I18n] Language changed to: ${locale}`);
    });
  }

  /**
   * Apply language to all elements with data-i18n attributes
   */
  applyLanguage() {
    // Set html lang attribute
    document.documentElement.lang = this.currentLocale;

    // Update text content
    document.querySelectorAll('[data-i18n]').forEach(element => {
      const key = element.getAttribute('data-i18n');
      const params = this.parseParams(element.getAttribute('data-i18n-params'));
      element.textContent = this.t(key, params);
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
      const key = element.getAttribute('data-i18n-placeholder');
      element.placeholder = this.t(key);
    });

    // Update titles
    document.querySelectorAll('[data-i18n-title]').forEach(element => {
      const key = element.getAttribute('data-i18n-title');
      element.title = this.t(key);
    });

    // Update aria-labels
    document.querySelectorAll('[data-i18n-aria]').forEach(element => {
      const key = element.getAttribute('data-i18n-aria');
      element.setAttribute('aria-label', this.t(key));
    });

    // Update select options
    document.querySelectorAll('[data-i18n-option]').forEach(option => {
      const key = option.getAttribute('data-i18n-option');
      option.textContent = this.t(key);
    });

    console.log(`[I18n] Applied language: ${this.currentLocale}`);
    
    // Trigger a custom event so other parts of the app can react to language change
    window.dispatchEvent(new CustomEvent('languageChanged', { 
      detail: { locale: this.currentLocale } 
    }));
  }

  /**
   * Parse JSON params from attribute string
   */
  parseParams(paramsStr) {
    if (!paramsStr) {
      return {};
    }
    try {
      return JSON.parse(paramsStr);
    } catch (e) {
      console.warn('[I18n] Failed to parse params:', paramsStr, e);
      return {};
    }
  }

  /**
   * Get current locale
   */
  getLocale() {
    return this.currentLocale;
  }

  /**
   * Get all supported locales
   */
  getSupportedLocales() {
    return this.supportedLocales;
  }
}

// Create global instance
window.i18n = new I18nManager();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = window.i18n;
}
