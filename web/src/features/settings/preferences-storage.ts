export const DEVTOOLS_STORAGE_KEY = 'scientific_workspace_react_query_devtools_v1';
export const DEVTOOLS_EVENT = 'scientific_workspace_devtools_changed';

export function readDevtoolsPreference(storage: Pick<Storage, 'getItem'> = window.localStorage) {
  return storage.getItem(DEVTOOLS_STORAGE_KEY) === 'true';
}

export function writeDevtoolsPreference(
  enabled: boolean,
  storage: Pick<Storage, 'setItem'> = window.localStorage
) {
  storage.setItem(DEVTOOLS_STORAGE_KEY, String(enabled));
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(DEVTOOLS_EVENT));
}
