import { computed, ref } from "vue";

import enUS from "../locales/en-US.json";
import zhCN from "../locales/zh-CN.json";

const STORAGE_KEY = "app_locale"; // zh-CN | en-US
const dictionaries = { "zh-CN": zhCN, "en-US": enUS };
const localeRef = ref(localStorage.getItem(STORAGE_KEY) || "zh-CN");

const lookup = (dict, key) =>
  key.split(".").reduce((acc, part) => (acc == null ? undefined : acc[part]), dict);

const interpolate = (template, params) => {
  if (!params || typeof template !== "string") return template;
  return template.replace(/\{(\w+)\}/g, (match, key) =>
    params[key] === undefined ? match : String(params[key]),
  );
};

export function useI18n() {
  const locale = computed(() => localeRef.value);
  const t = (key, params) => {
    const current = lookup(dictionaries[localeRef.value] || zhCN, key);
    if (current != null) return interpolate(current, params);
    const fallback = lookup(zhCN, key);
    return fallback != null ? interpolate(fallback, params) : key;
  };
  const setLocale = (value) => {
    if (!dictionaries[value]) return;
    localeRef.value = value;
    localStorage.setItem(STORAGE_KEY, value);
    document.documentElement.lang = value;
  };
  document.documentElement.lang = localeRef.value;
  return { locale, t, setLocale };
}
