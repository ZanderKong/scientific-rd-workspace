#!/usr/bin/env bash
set -euo pipefail

api_url="${API_URL:-http://127.0.0.1:8000/api/v1}"
web_url="${WEB_URL:-http://127.0.0.1:3000}"
artifact_dir="${ARTIFACT_DIR:-output/playwright/plan10-first-run}"
session="${PLAYWRIGHT_CLI_SESSION:-plan10-first-run-browser-smoke}"
run_label="${GITHUB_RUN_ID:-local}"
sample_title="Plan 10 first-run sample ${run_label}"

repo_root="$(pwd)"
if [[ "$artifact_dir" != /* ]]; then artifact_dir="${repo_root}/${artifact_dir}"; fi
mkdir -p "$artifact_dir"
cd "$artifact_dir"

pw() {
  if [[ -n "${PWCLI_PATH:-}" ]]; then
    "$PWCLI_PATH" --session "$session" "$@"
  else
    npx --yes --package @playwright/cli playwright-cli --session "$session" "$@"
  fi
}

run_code() { pw run-code "async (page) => { $1 }"; }
snapshot() { local name="$1"; pw snapshot > "${name}.snapshot.txt"; }
assert_snapshot() { local name="$1"; local pattern="$2"; grep -Fq -- "$pattern" "${name}.snapshot.txt"; }

pw open "$web_url/dashboard/samples"
pw resize 1440 900
run_code "const picker = page.getByRole('button', {name: '新建或选择项目'}); if (!(await picker.isVisible())) { await page.getByRole('button', {name: '切换侧边栏'}).click(); await page.waitForTimeout(150); } await picker.click(); const menu = page.getByTestId('project-switcher-menu'); await menu.getByRole('button', {name: '新建项目'}).click(); await page.getByRole('textbox', {name: /项目名称/}).fill('Gas Sensor Development'); await page.getByRole('button', {name: '新建项目'}).last().click(); await page.waitForTimeout(500)"
snapshot 01-project-created
assert_snapshot 01-project-created 'GSD'
assert_snapshot 01-project-created 'Gas Sensor Development'
run_code "await page.getByRole('button', {name: '新建样品'}).click(); await page.getByRole('textbox', {name: 'Sample 标题'}).fill('${sample_title}'); await page.getByRole('textbox', {name: '第 1 个 Process'}).press('/'); await page.waitForTimeout(200); await page.getByText('自定义过程').click(); await page.getByTestId('save-sample-record').click(); await page.waitForSelector('[data-testid=sample-success]')"
snapshot 02-sample-created
assert_snapshot 02-sample-created 'Sample Record 已保存'

run_code "await page.getByRole('link', {name: '设备'}).click(); await page.waitForTimeout(500); await page.getByRole('link', {name: '新建设备'}).click(); await page.getByRole('textbox', {name: /设备名称/}).fill('Mixing Station 01'); await page.getByRole('textbox', {name: /资产编号/}).fill('MX-01'); await page.getByRole('textbox', {name: /制造商/}).fill('Demo'); await page.getByRole('textbox', {name: /型号/}).fill('M100'); await page.getByRole('textbox', {name: /位置/}).fill('Lab A'); await page.getByRole('button', {name: '添加字段'}).click(); await page.getByRole('textbox', {name: '显示名称'}).fill('转速'); await page.getByRole('textbox', {name: '稳定 key'}).fill('rpm'); await page.getByRole('textbox', {name: '默认单位'}).fill('rpm'); await page.getByRole('button', {name: '添加'}).click(); await page.getByRole('button', {name: '添加字段'}).click(); await page.getByRole('textbox', {name: '显示名称'}).fill('时间'); await page.getByRole('textbox', {name: '稳定 key'}).fill('duration'); await page.getByRole('textbox', {name: '默认单位'}).fill('min'); await page.getByRole('button', {name: '添加'}).click(); await page.getByRole('button', {name: '新建设备'}).last().click(); await page.waitForTimeout(500)"
snapshot 03-equipment
assert_snapshot 03-equipment 'Mixing Station 01'
run_code "await page.getByRole('link', {name: '编辑'}).click(); await page.getByRole('textbox', {name: /型号/}).fill('M200'); await page.getByRole('button', {name: '保存更改'}).click(); await page.waitForTimeout(500); if (!(await page.getByText('M200').count())) throw new Error('equipment edit did not persist')"
snapshot 04-equipment-edit
assert_snapshot 04-equipment-edit 'M200'

run_code "await page.getByRole('link', {name: '样品'}).click(); await page.waitForTimeout(400); await page.getByRole('button', {name: '新建样品'}).click(); await page.getByRole('textbox', {name: '资源解析器'}).fill('@Mixing Station 01'); await page.waitForTimeout(500); if (!(await page.getByText('Mixing Station 01').count())) throw new Error('equipment missing from Sample resolver'); await page.getByRole('button', {name: /Mixing Station 01/}).first().click(); if (!(await page.getByTestId('usage-fields').count())) throw new Error('equipment usage fields missing from Sample resolver')"
snapshot 05-equipment-resolver
assert_snapshot 05-equipment-resolver 'rpm'
assert_snapshot 05-equipment-resolver 'duration'

run_code "await page.getByRole('link', {name: '数据'}).click(); await page.waitForTimeout(400)"
snapshot 06-data-landing
assert_snapshot 06-data-landing '数据工作区将在下一阶段完成'
if grep -Fq -- '新建数据' 06-data-landing.snapshot.txt || grep -Fq -- '上传数据' 06-data-landing.snapshot.txt; then echo 'Data landing exposed an unplanned write action' >&2; exit 1; fi

run_code "const gear = page.getByRole('button', {name: '设置'}); await gear.hover(); await page.waitForTimeout(350)"
snapshot 07-settings-hover
assert_snapshot 07-settings-hover '快捷设置'
run_code "const before = page.url(); await page.getByRole('button', {name: 'English'}).click(); await page.waitForTimeout(400); if (page.url() !== before) throw new Error('locale changed the route')"
snapshot 08-settings-english
assert_snapshot 08-settings-english 'Quick settings'
run_code "await page.getByRole('button', {name: 'Settings'}).click(); await page.waitForTimeout(400)"
snapshot 09-settings-page
assert_snapshot 09-settings-page 'Settings'
run_code "await page.getByRole('button', {name: 'Dark'}).click(); await page.getByRole('button', {name: '中文'}).click(); await page.waitForTimeout(300); if (await page.getByText('TanStack Query Devtools').count()) throw new Error('devtools is visible by default')"

run_code "await page.getByRole('button', {name: /Gas Sensor Development/}).click(); await page.getByTestId('project-switcher-menu').getByRole('button', {name: '编辑项目标识'}).click(); await page.getByRole('textbox', {name: '自定义头像文字'}).fill('GSR'); await page.getByRole('button', {name: '保存'}).click(); await page.waitForTimeout(200)"
snapshot 10-custom-avatar
assert_snapshot 10-custom-avatar 'GSR'
run_code "await page.getByRole('button', {name: /Gas Sensor Development/}).click(); await page.getByTestId('project-switcher-menu').getByRole('button', {name: '编辑项目标识'}).click(); await page.getByRole('button', {name: '恢复自动'}).click(); await page.waitForTimeout(200)"
snapshot 11-auto-avatar
assert_snapshot 11-auto-avatar 'GSD'

printf '%s\n' 'Plan 10 first-run browser acceptance passed' > browser-acceptance.txt
pw close
