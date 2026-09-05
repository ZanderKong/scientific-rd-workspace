# Sample Recording v0.3

Sample recording is a projection over a tagged `research_object` and Process Executions.

```text
GET  /api/v1/samples/{id}/record
POST /api/v1/sample-records
PUT  /api/v1/samples/{id}/record
```

Each draft step selects a Process Definition and optional pinned version. The aggregate request may include multiple Research Object and Data bindings, field values and outputs. The service appends the Sample context binding and returns ordered execution projections. It never creates a legacy Process object or one-to-one SampleExecution.

Data subject and derived-from shortcuts are maintained by the execution service. A branched execution graph is returned explicitly; clients must not silently flatten it.
