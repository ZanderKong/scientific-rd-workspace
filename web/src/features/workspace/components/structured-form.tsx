'use client';

import { useMemo } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import type { Translator, UISchemaElement } from '@jsonforms/core';
import { JsonForms } from '@jsonforms/react';
import { vanillaCells, vanillaRenderers } from '@jsonforms/vanilla-renderers';
import type { JsonObject } from '@/lib/domain';
import { buildStructuredUiSchema } from '@/lib/structured-ui-schema';
import { parseLocale } from '@/i18n/config';

const FIELD_TRANSLATION_KEYS = {
  'Primary material': 'primaryMaterial',
  'Material concentration': 'materialConcentration',
  Solvent: 'solvent',
  Additives: 'additives',
  Name: 'name',
  Amount: 'amount',
  Unit: 'unit',
  'Drying temperature': 'dryingTemperature',
  'Drying time': 'dryingTime',
  Substrate: 'substrate'
} as const;
const PRESENTATION_TRANSLATION_KEYS = {
  Value: 'value',
  None: 'none',
  Add: 'add',
  Delete: 'delete',
  Valid: 'valid',
  Items: 'items',
  Up: 'up',
  Down: 'down',
  'No data': 'noData',
  'No selection': 'noSelection',
  'Confirm Deletion': 'confirmDeletion',
  Yes: 'yes',
  No: 'no'
} as const;
type FormTranslationKey =
  | (typeof FIELD_TRANSLATION_KEYS)[keyof typeof FIELD_TRANSLATION_KEYS]
  | (typeof PRESENTATION_TRANSLATION_KEYS)[keyof typeof PRESENTATION_TRANSLATION_KEYS]
  | 'addTo'
  | 'deleteButton'
  | 'moveItemUp'
  | 'moveItemDown'
  | 'noData'
  | 'noSelection';

type JsonFormsError = { keyword: string; message?: string };

function translateSchemaTitles(
  value: unknown,
  translate: (key: FormTranslationKey) => string
): unknown {
  if (Array.isArray(value)) return value.map((item) => translateSchemaTitles(item, translate));
  if (!value || typeof value !== 'object') return value;

  const result: JsonObject = {};
  for (const [key, child] of Object.entries(value)) {
    if (key === 'properties' && child && typeof child === 'object' && !Array.isArray(child)) {
      result[key] = Object.fromEntries(
        Object.entries(child).map(([propertyKey, propertySchema]) => {
          const translatedSchema = translateSchemaTitles(propertySchema, translate);
          if (
            !translatedSchema ||
            typeof translatedSchema !== 'object' ||
            Array.isArray(translatedSchema)
          ) {
            return [propertyKey, translatedSchema];
          }
          const property = translatedSchema as JsonObject;
          if (typeof property.title !== 'string') {
            const defaultTitle = propertyKey
              .replaceAll('_', ' ')
              .replace(/^./, (letter) => letter.toUpperCase());
            property.title = resolveFormTranslation('', defaultTitle, translate) ?? defaultTitle;
          }
          return [propertyKey, property];
        })
      );
      continue;
    }
    result[key] =
      key === 'title' && typeof child === 'string'
        ? (resolveFormTranslation('', child, translate) ?? child)
        : translateSchemaTitles(child, translate);
  }
  return result;
}

export function resolveFormTranslation(
  key: string,
  defaultMessage: string | undefined,
  translate: (key: FormTranslationKey) => string
): string | undefined {
  const field = defaultMessage?.trim();
  if (!field) return defaultMessage;
  const required = field.endsWith('*');
  const base = required ? field.slice(0, -1) : field;
  const translationKey =
    FIELD_TRANSLATION_KEYS[base as keyof typeof FIELD_TRANSLATION_KEYS] ??
    PRESENTATION_TRANSLATION_KEYS[base as keyof typeof PRESENTATION_TRANSLATION_KEYS];
  if (translationKey) return `${translate(translationKey)}${required ? '*' : ''}`;
  if (field.startsWith('Add to ')) {
    return `${translate('addTo')} ${field.slice('Add to '.length)}`;
  }
  if (field === 'Delete button') return translate('deleteButton');
  if (field === 'Move item up') return translate('moveItemUp');
  if (field === 'Move item down') return translate('moveItemDown');
  return defaultMessage;
}

export function StructuredForm({
  schema,
  uiSchema,
  data,
  onChange,
  readonly = false
}: {
  schema: JsonObject;
  uiSchema?: JsonObject | null;
  data: JsonObject;
  onChange?: (data: JsonObject) => void;
  readonly?: boolean;
}) {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Forms');
  const presentationSchema = useMemo(
    () => translateSchemaTitles(schema, (translationKey) => t(translationKey)) as JsonObject,
    [schema, t]
  );
  const resolvedUiSchema = useMemo(
    () => (uiSchema ?? buildStructuredUiSchema(presentationSchema)) as UISchemaElement,
    [presentationSchema, uiSchema]
  );
  const i18n = useMemo(
    () => ({
      locale,
      translate: ((key: string, defaultMessage?: string) =>
        resolveFormTranslation(key, defaultMessage, (translationKey) =>
          t(translationKey)
        )) as Translator,
      translateError: (error: JsonFormsError) => {
        if (error.keyword === 'required') return t('required');
        if (error.keyword === 'type') return t('invalidType');
        return error.message ?? t('invalidType');
      }
    }),
    [locale, t]
  );
  return (
    <div className='jsonforms-shell rounded-lg border bg-background p-4'>
      <JsonForms
        schema={presentationSchema}
        uischema={resolvedUiSchema}
        data={data}
        renderers={vanillaRenderers}
        cells={vanillaCells}
        readonly={readonly}
        validationMode='ValidateAndShow'
        i18n={i18n}
        onChange={({ data: next }) => {
          if (!readonly) onChange?.((next ?? {}) as JsonObject);
        }}
      />
    </div>
  );
}
