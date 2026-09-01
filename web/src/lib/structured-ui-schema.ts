import type { GroupLayout, UISchemaElement, VerticalLayout } from '@jsonforms/core';
import type { JsonObject } from './domain';

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function pointerSegment(value: string): string {
  return value.replaceAll('~', '~0').replaceAll('/', '~1');
}

function labelFor(key: string, schema: JsonObject): string {
  return typeof schema.title === 'string'
    ? schema.title
    : key.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
}

function buildElements(schema: JsonObject, scope: string): UISchemaElement[] {
  if (!isObject(schema.properties)) return [];
  return Object.entries(schema.properties).map(([key, rawProperty]) => {
    const property = isObject(rawProperty) ? rawProperty : {};
    const propertyScope = `${scope}/properties/${pointerSegment(key)}`;
    if ((property.type === 'object' || isObject(property.properties)) && property.properties) {
      return {
        type: 'Group',
        label: labelFor(key, property),
        elements: buildElements(property, propertyScope)
      } satisfies GroupLayout;
    }
    return { type: 'Control', scope: propertyScope };
  });
}

export function buildStructuredUiSchema(schema: JsonObject): VerticalLayout {
  return { type: 'VerticalLayout', elements: buildElements(schema, '#') };
}
