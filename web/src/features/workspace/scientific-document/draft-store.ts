import type { JsonObject } from '@/lib/domain';

const DATABASE_NAME = 'scientific-workspace-drafts';
const STORE_NAME = 'scientific-records';
const DATABASE_VERSION = 1;

export interface ScientificLocalDraft {
  format_version: 1;
  key: string;
  record_id: string | null;
  project_id: string;
  base_record_sha256: string | null;
  saved_at: string;
  title: string;
  status: string;
  tags: string;
  blocks: JsonObject[];
}

function database(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === 'undefined') return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.addEventListener('upgradeneeded', () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: 'key' });
      }
    });
    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error));
  });
}

export async function readScientificDraft(key: string): Promise<ScientificLocalDraft | null> {
  const db = await database();
  if (!db) return null;
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readonly');
    const request = transaction.objectStore(STORE_NAME).get(key);
    request.addEventListener('success', () =>
      resolve((request.result as ScientificLocalDraft | undefined) ?? null)
    );
    request.addEventListener('error', () => reject(request.error));
    transaction.addEventListener('complete', () => db.close());
  });
}

export async function writeScientificDraft(draft: ScientificLocalDraft): Promise<void> {
  const db = await database();
  if (!db) return;
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readwrite');
    transaction.objectStore(STORE_NAME).put(structuredClone(draft));
    transaction.addEventListener('complete', () => {
      db.close();
      resolve();
    });
    transaction.addEventListener('error', () => reject(transaction.error));
  });
}

export async function deleteScientificDraft(key: string): Promise<void> {
  const db = await database();
  if (!db) return;
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readwrite');
    transaction.objectStore(STORE_NAME).delete(key);
    transaction.addEventListener('complete', () => {
      db.close();
      resolve();
    });
    transaction.addEventListener('error', () => reject(transaction.error));
  });
}
