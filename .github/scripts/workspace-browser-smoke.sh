#!/usr/bin/env bash
set -euo pipefail

api_url="${API_URL:-http://127.0.0.1:8000/api/v1}"
web_url="${WEB_URL:-http://127.0.0.1:3000}"
artifact_dir="${ARTIFACT_DIR:-output/playwright/workspace}"
session="${PLAYWRIGHT_CLI_SESSION:-workspace-browser-smoke}"

repo_root="$(pwd)"
if [[ "$artifact_dir" != /* ]]; then
  artifact_dir="${repo_root}/${artifact_dir}"
fi
mkdir -p "$artifact_dir"
cd "$artifact_dir"

pw() {
  if [[ -n "${PWCLI_PATH:-}" ]]; then
    "$PWCLI_PATH" --session "$session" "$@"
  else
    npx --yes --package @playwright/cli playwright-cli --session "$session" "$@"
  fi
}

wait_for_app() {
  pw run-code "async (page) => { await page.waitForTimeout(800); }"
}

snapshot() {
  local name="$1"
  pw snapshot > "${name}.snapshot.txt"
}

assert_snapshot() {
  local name="$1"
  local pattern="$2"
  grep -Fq -- "$pattern" "${name}.snapshot.txt"
}

resolve_id() {
  local kind="$1"
  local code="$2"
  local scope_filter="&include_global=false"
  if [[ "$kind" == "project" ]]; then
    scope_filter=""
  fi
  curl --fail --silent --show-error \
    "$api_url/objects?kind=${kind}&q=${code}${scope_filter}&limit=1" \
    | jq -r '.[0].id // empty'
}

project_id="$(resolve_id project PRJ-001)"
experiment_id="$(resolve_id experiment EXP-001)"
data_id="$(resolve_id data DAT-001)"
sample_id="$(resolve_id sample SMP-001)"
for pair in "project:${project_id}" "experiment:${experiment_id}" "data:${data_id}" "sample:${sample_id}"; do
  if [[ "$pair" == *: ]]; then
    echo "Unable to resolve seeded object: ${pair%%:*}" >&2
    exit 1
  fi
done

pw open "$web_url/dashboard/projects/$project_id"
wait_for_app
pw resize 1440 900
snapshot 01-project
assert_snapshot 01-project 'Project record'
assert_snapshot 01-project '项目检索'
pw screenshot --filename 01-project-1440.png --full-page

pw open "$web_url/dashboard/experiments?project=$project_id"
wait_for_app
snapshot 02-experiments
assert_snapshot 02-experiments '实验记录'
assert_snapshot 02-experiments '新建 Experiment'
pw screenshot --filename 02-experiments-1440.png --full-page

pw open "$web_url/dashboard/experiments/$experiment_id"
wait_for_app
snapshot 03-experiment-detail
assert_snapshot 03-experiment-detail 'Deterministic comparison'
assert_snapshot 03-experiment-detail 'Experiment members'
assert_snapshot 03-experiment-detail 'XY series'
pw screenshot --filename 03-experiment-detail-1440.png --full-page

pw open "$web_url/dashboard/data/$data_id"
wait_for_app
snapshot 04-data-detail
assert_snapshot 04-data-detail 'Data record / DAT-001'
assert_snapshot 04-data-detail 'scalar'
pw resize 1024 900
pw screenshot --filename 04-data-detail-1024.png --full-page

pw open "$web_url/dashboard/samples/$sample_id"
wait_for_app
snapshot 05-sample-execution
assert_snapshot 05-sample-execution 'Sample Execution'
assert_snapshot 05-sample-execution '开始执行'
pw screenshot --filename 05-sample-execution-1024.png --full-page

pw open "$web_url/dashboard/changes?project=$project_id"
wait_for_app
snapshot 06-change-review
assert_snapshot 06-change-review '变更审核'
assert_snapshot 06-change-review 'Change review'
pw screenshot --filename 06-change-review-1024.png --full-page

printf '%s\n' "Scientific Workspace browser acceptance passed" > browser-acceptance.txt
printf '%s\n' "project=${project_id}" "experiment=${experiment_id}" "data=${data_id}" "sample=${sample_id}" >> browser-acceptance.txt
pw close
