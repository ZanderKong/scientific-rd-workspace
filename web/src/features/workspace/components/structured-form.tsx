'use client';

import { JsonForms } from '@jsonforms/react';
import { vanillaCells, vanillaRenderers } from '@jsonforms/vanilla-renderers';
import type { JsonObject } from '@/lib/domain';

export function StructuredForm({
  schema,
  data,
  onChange,
  readonly = false
}: {
  schema: JsonObject;
  data: JsonObject;
  onChange: (data: JsonObject) => void;
  readonly?: boolean;
}) {
  return (
    <div className='jsonforms-shell rounded-lg border bg-background p-4'>
      <JsonForms
        schema={schema}
        data={data}
        renderers={vanillaRenderers}
        cells={vanillaCells}
        readonly={readonly}
        validationMode='ValidateAndShow'
        onChange={({ data: next }) => onChange((next ?? {}) as JsonObject)}
      />
    </div>
  );
}
