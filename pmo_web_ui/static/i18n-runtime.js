// static/i18n-runtime.js - i18n / language runtime
// Extracted from index.html (RFC-2 slice 2)

let _lang = localStorage.getItem('pmo_lang') || 'en';

function lang() { return _lang; }

function t(key) {
  return T[_lang]?.[key] ?? T['en']?.[key] ?? key;
}

function setLang(l) {
  _lang = l;
  localStorage.setItem('pmo_lang', l);
  applyTranslations();
}

function toggleLang() {
  setLang(_lang === 'en' ? 'zh' : 'en');
}

function applyTranslations() {
  // Apply data-i18n attributes — elements with this attr get their text replaced
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  // Apply placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });
}
