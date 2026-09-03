#!/usr/bin/env bash
set -euo pipefail

api_url="${API_URL:-http://127.0.0.1:8000/api/v1}"
web_url="${WEB_URL:-http://127.0.0.1:3000}"
artifact_dir="${ARTIFACT_DIR:-output/playwright/plan08}"
session="${PLAYWRIGHT_CLI_SESSION:-plan08-browser-smoke}"
project_code="${PROJECT_CODE:-PRJ-001}"
run_label="${GITHUB_RUN_ID:-local}"
sample_title="Plan 08 browser ${run_label}"
clone_title="Plan 08 browser clone ${run_label}"

mkdir -p "$artifact_dir"
cd "$artifact_dir"

pw() {
  if [[ -n "${PWCLI_PATH:-}" ]]; then
    "$PWCLI_PATH" --session "$session" "$@"
  else
    npx --yes --package @playwright/cli playwright-cli --session "$session" "$@"
  fi
}

snapshot() {
  local name="$1"
  pw snapshot > "${name}.snapshot.txt"
}

assert_snapshot() {
  local name="$1"
  local pattern="$2"
  rg -q "$pattern" "${name}.snapshot.txt"
}

project_json="$(curl --fail --silent --show-error "$api_url/objects?kind=project&q=${project_code}&limit=1")"
project_id="$(jq -r '.[0].id // empty' <<<"$project_json")"
if [[ -z "$project_id" ]]; then
  echo "Unable to resolve seeded project ${project_code}" >&2
  exit 1
fi

pw open "$web_url/dashboard/samples"
pw resize 1440 900
snapshot 01-samples
assert_snapshot 01-samples 'Samples'
assert_snapshot 01-samples '新建 Sample'

pw run-code "await page.getByRole('combobox', {name: 'Project Scope'}).selectOption('${project_id}'); await page.waitForTimeout(500)"
snapshot 02-scoped-samples
assert_snapshot 02-scoped-samples '新建 Sample'
pw screenshot --filename 02-scoped-samples-1440.png --full-page

pw run-code "await page.getByRole('button', {name: '新建 Sample'}).click(); await page.waitForTimeout(500)"
snapshot 03-new-composer
assert_snapshot 03-new-composer 'Process Blocks'
assert_snapshot 03-new-composer '第 1 个 Process'

pw run-code "await page.getByRole('textbox', {name: 'Sample 标题'}).fill('${sample_title}')"
pw run-code "await page.getByRole('textbox', {name: '第 1 个 Process'}).press('/'); await page.waitForTimeout(250)"
snapshot 04-process-command
assert_snapshot 04-process-command '自定义过程'
pw press ArrowDown
pw press Enter
snapshot 05-process-selected
assert_snapshot 05-process-selected '过程 / 操作'

pw run-code "const input = page.getByRole('textbox', {name: '资源解析器'}); await input.fill('@7681-11-0'); await page.waitForTimeout(500)"
snapshot 06-material-resolver
assert_snapshot 06-material-resolver 'Potassium iodide'
pw run-code "const resolver = page.getByTestId('resource-resolver'); if (!(await resolver.innerText()).includes('身份来自对象库')) throw new Error('material identity preview missing')"
pw run-code "await page.getByRole('button', {name: /Potassium iodide/}).first().click(); await page.waitForTimeout(200)"

pw run-code "const input = page.getByRole('textbox', {name: '资源解析器'}); await input.fill('@DEMO-IMP'); await page.waitForTimeout(500)"
snapshot 07-equipment-resolver
assert_snapshot 07-equipment-resolver 'Impregnation setup'
pw run-code "await page.getByRole('button', {name: /Impregnation setup/}).first().click(); await page.waitForTimeout(200)"

pw run-code "const strip = page.getByTestId('resource-token-strip'); if (await strip.locator('button').count() !== 2) throw new Error('expected mixed Material and Equipment tokens'); const classes = await Promise.all([strip.locator('button').nth(0).getAttribute('class'), strip.locator('button').nth(1).getAttribute('class')]); if (!classes.some((value) => value?.includes('amber')) || !classes.some((value) => value?.includes('sky'))) throw new Error('semantic token colors missing'); const text = await strip.innerText(); if (text.includes('原料') || text.includes('设备')) throw new Error('token strip has category heading')"

pw run-code "const usage = page.getByTestId('usage-fields'); await usage.nth(0).getByRole('spinbutton').fill('5'); await usage.nth(1).getByRole('spinbutton').nth(0).fill('700'); await usage.nth(1).getByRole('spinbutton').nth(1).fill('12')"
pw run-code "const usage = page.getByTestId('usage-fields').nth(1); await usage.getByRole('button', {name: '+ 属性'}).click(); await usage.getByRole('textbox', {name: '属性 key'}).fill('torque'); await usage.getByRole('button', {name: '添加'}).click(); await usage.getByRole('spinbutton').last().fill('2')"

pw run-code "await page.getByRole('button', {name: '添加 Process'}).first().click(); await page.getByRole('textbox', {name: '第 2 个 Process'}).fill('Drying'); await page.waitForTimeout(200)"
snapshot 08-composer-filled
assert_snapshot 08-composer-filled 'Drying'
pw screenshot --filename 08-composer-filled-1440.png --full-page

pw run-code "await page.getByTestId('save-sample-record').click(); await page.waitForSelector('[data-testid=sample-success]');"
snapshot 09-create-success
assert_snapshot 09-create-success 'Sample Record 已保存'
pw screenshot --filename 09-create-success-1440.png --full-page

sample_query="$(jq -rn --arg value "$sample_title" '$value | @uri')"
created_json="$(curl --fail --silent --show-error "$api_url/objects?kind=sample&q=${sample_query}&project_scope_id=${project_id}&include_global=false&limit=10")"
sample_id="$(jq -r --arg title "$sample_title" '.[] | select(.title == $title) | .id' <<<"$created_json" | head -n 1)"
if [[ -z "$sample_id" ]]; then
  echo "Browser-created Sample was not found through the API" >&2
  exit 1
fi

pw run-code "await page.getByRole('link', {name: '查看样品'}).click(); await page.waitForTimeout(500)"
snapshot 10-detail
assert_snapshot 10-detail '当前 Data / provenance'
assert_snapshot 10-detail 'Process step'
pw screenshot --filename 10-detail-1440.png --full-page

pw run-code "await page.getByRole('button', {name: '编辑记录'}).click(); await page.waitForTimeout(300)"
snapshot 11-edit-composer
assert_snapshot 11-edit-composer '编辑 Sample Record'
pw resize 1024 900
pw screenshot --filename 11-edit-composer-1024.png --full-page

pw run-code "await page.getByRole('button', {name: '取消'}).click(); await page.waitForTimeout(200); await page.getByRole('button', {name: '基于此样品新建'}).click(); await page.waitForTimeout(500)"
snapshot 12-clone-draft
assert_snapshot 12-clone-draft '记录一个新 Sample'
pw run-code "await page.getByRole('textbox', {name: 'Sample 标题'}).fill('${clone_title}')"
pw run-code "await page.getByTestId('save-sample-record').click(); await page.waitForSelector('[data-testid=sample-success]');"
snapshot 13-clone-success
assert_snapshot 13-clone-success 'Sample Record 已保存'
pw screenshot --filename 13-clone-success-1024.png --full-page

clone_query="$(jq -rn --arg value "$clone_title" '$value | @uri')"
clones_json="$(curl --fail --silent --show-error "$api_url/objects?kind=sample&q=${clone_query}&project_scope_id=${project_id}&include_global=false&limit=10")"
clone_id="$(jq -r --arg title "$clone_title" '.[] | select(.title == $title) | .id' <<<"$clones_json" | head -n 1)"
if [[ -z "$clone_id" || "$clone_id" == "$sample_id" ]]; then
  echo "Clone did not create a distinct Sample ID" >&2
  exit 1
fi

source_record="$(curl --fail --silent --show-error "$api_url/samples/${sample_id}/record")"
clone_record="$(curl --fail --silent --show-error "$api_url/samples/${clone_id}/record")"
source_material_id="$(jq -r '.steps[0].resources[] | select(.object.kind == "material") | .object.id' <<<"$source_record" | head -n 1)"
source_equipment_id="$(jq -r '.steps[0].resources[] | select(.object.kind == "equipment") | .object.id' <<<"$source_record" | head -n 1)"
clone_material_id="$(jq -r '.steps[0].resources[] | select(.object.kind == "material") | .object.id' <<<"$clone_record" | head -n 1)"
clone_equipment_id="$(jq -r '.steps[0].resources[] | select(.object.kind == "equipment") | .object.id' <<<"$clone_record" | head -n 1)"
[[ -n "$source_material_id" && "$source_material_id" == "$clone_material_id" ]]
[[ -n "$source_equipment_id" && "$source_equipment_id" == "$clone_equipment_id" ]]
[[ "$(jq -r '.sample.title' <<<"$source_record")" == "$sample_title" ]]
[[ "$(jq -r '.sample.title' <<<"$clone_record")" == "$clone_title" ]]
source_process_ids="$(jq -r '.steps[].process.id' <<<"$source_record")"
clone_process_ids="$(jq -r '.steps[].process.id' <<<"$clone_record")"
while read -r source_process_id; do
  [[ -z "$source_process_id" ]] || ! grep -Fqx "$source_process_id" <<<"$clone_process_ids"
done <<<"$source_process_ids"

printf '%s\n' "Plan 08 browser acceptance passed" > browser-acceptance.txt
printf '%s\n' "source_sample=${sample_id}" "clone_sample=${clone_id}" "material=${source_material_id}" "equipment=${source_equipment_id}" >> browser-acceptance.txt
pw close
