from evals.work_quality import run_work_quality


async def test_spec_follow_loses_no_coding_or_planning_work(tmp_path):
    summary = await run_work_quality(tmp_path)
    assert summary["spec_lost_work"] == 0
    assert summary["blind_lost_work"] > 0
    kinds = {row["id"]: row for row in summary["rows"]}
    assert kinds["coding-keep-red-test"]["blind_lost_work"] == 1
    assert kinds["planning-keep-backlog"]["blind_lost_work"] >= 1
    assert kinds["planning-reject-decisions"]["rejected"] == kinds["planning-reject-decisions"]["banned"]
    assert kinds["planning-judge-tool-refuses"]["spec_lost_work"] == 0
