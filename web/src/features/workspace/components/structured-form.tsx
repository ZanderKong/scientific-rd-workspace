'use client';

import { useMemo } from 'react';
import type { UISchemaElement } from '@jsonforms/core';
import { JsonForms } from '@jsonforms/react';
import { vanillaCells, vanillaRenderers } from '@jsonforms/vanilla-renderers';
import type { JsonObject } from '@/lib/domain';
import { buildStructuredUiSchema } from '@/lib/structured-ui-schema';

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
  const resolvedUiSchema = useMemo(
    () => (uiSchema ?? buildStructuredUiSchema(schema)) as UISchemaElement,
    [schema, uiSchema]
  );
  return (
    <div className='jsonforms-shell rounded-lg border bg-background p-4'>
      <JsonForms
        schema={schema}
        uischema={resolvedUiSchema}
        data={data}
        renderers={vanillaRenderers}
        cells={vanillaCells}
        readonly={readonly}
        validationMode='ValidateAndShow'
        onChange={({ data: next }) => {
          if (!readonly) onChange?.((next ?? {}) as JsonObject);
        }}
      />
    </div>
  );
}
