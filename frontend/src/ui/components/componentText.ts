import type { ComponentInfo } from '../../domain/types';
import { isMessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';

/** The description of a component in the current language, or the backend's as a fallback. */
export function useComponentDescription(): (component: ComponentInfo) => string {
  const { t } = useI18n();
  return (component) => {
    const key = `component.${component.implementationId}`;
    return isMessageKey(key) ? t(key) : component.description;
  };
}

/** The label of a component's parameter in the current language, or its raw name. */
export function useParamLabel(): (implementationId: string, name: string) => string {
  const { t } = useI18n();
  return (implementationId, name) => {
    const key = `param.${implementationId}.${name}`;
    return isMessageKey(key) ? t(key) : name;
  };
}
