# Sample Recording API Examples

All examples use the `/api/v1` prefix and placeholder UUIDs. The endpoint writes one aggregate transaction.

## Create a two-step record

```bash
curl -X POST http://localhost:8000/api/v1/sample-records \
  -H 'Content-Type: application/json' \
  -d '{
    "project_scope_id": "PROJECT_UUID",
    "sample": {
      "title": "KI chlorine strip",
      "status": "draft"
    },
    "steps": [
      {
        "title": "Mixing",
        "type_version_id": "MIXING_TYPE_VERSION_UUID",
        "properties_jsonb": {
          "parameters": {
            "temperature": { "value": 25, "unit": "°C" }
          }
        },
        "resources": [
          {
            "target_object_id": "MATERIAL_UUID",
            "role": "material",
            "usage_values": {
              "quantity": { "value": 10, "unit": "g" }
            }
          },
          {
            "target_object_id": "EQUIPMENT_UUID",
            "role": "equipment",
            "usage_values": {
              "rpm": { "value": 700, "unit": "rpm" }
            },
            "usage_schema_additions": [
              {
                "key": "torque",
                "label": "Torque",
                "value_type": "number",
                "default_unit": "N m",
                "options": [],
                "order": 1
              }
            ]
          }
        ]
      },
      {
        "title": "Drying",
        "resources": []
      }
    ],
    "change_note": "first recording"
  }'
```

The response includes the generated Sample and Process IDs. The final Process has `produces → Sample`; adjacent Process IDs have `precedes` relations. Material and Equipment objects are not mutated except for explicitly requested usage-schema additions.

## Read and edit

```bash
curl http://localhost:8000/api/v1/samples/SAMPLE_UUID/record

curl -X PUT http://localhost:8000/api/v1/samples/SAMPLE_UUID/record \
  -H 'Content-Type: application/json' \
  -d @desired-sample-record.json
```

`desired-sample-record.json` should contain the full ordered `steps` state. Retain a Process `process_id` to update it; omit it to add a new Process. Retain a resource `relation_id` where possible. Omit a safe existing step to archive it from the active chain.

## Inline Material example

```json
{
  "create_target": {
    "kind": "material",
    "title": "Potassium iodide",
    "properties_jsonb": { "cas": "7681-11-0" },
    "usage_schema_jsonb": {
      "fields": [
        {
          "key": "quantity",
          "label": "Quantity",
          "value_type": "number",
          "default_unit": "g",
          "options": [],
          "order": 0
        }
      ]
    }
  },
  "role": "material",
  "usage_values": { "quantity": { "value": 10, "unit": "g" } }
}
```

The inline object is created only if the final aggregate passes all semantic validation. If any final-step validation fails, the Sample, Process, inline object, relation, and schema changes are rolled back together.
