# Claude Code entry point

このrepositoryだけを読んで作業を開始しないでください。最初にcross-repository architecture
の正本であるzoo-hub（`git@github.com:kuntaro0524/zoo-hub.git`）を見つけ、次を読みます。

1. `zoo-hub/START_HERE.md`
2. `zoo-hub/HOW_TO_WORK.md`
3. `zoo-hub/docs/work-items/registry.md`
4. 対応するwork-item file

zoo-hubは隣接clone、site/environment固有の既知の場所、またはremote identityから探します。
見つからない場合はユーザーに場所を確認し、KAMOの古いoperation recordだけで新規workを開始しません。

既存作業は、registry → work-item → KAMOのbranch → 実際のGit HEAD/status → `Exact next action`
の順で復元します。新規作業は重複確認後にwork-itemをGitへ記録してから開始します。

KAMO固有の`AGENTS.md`、README、`doc/operations/README.md`、startup、handoffも確認します。
重要なdecisionと中断状態はconversationだけに残さず、work-itemとGitへ記録します。既知の
未追跡`XSCALE.LP`や他のunrelated変更を無断で変更、削除、commitしません。
