"""Revalidate the claimed approved feature against current source and target evidence."""


def scope_valid(engine, run):
    from .sources import load_records, load_reference_contents, target_completed
    from .planning import plan_features

    records = load_records(engine.repo)
    plans = plan_features(
        records,
        target_completed=target_completed(
            engine.repo, engine.settings.get("target_ref", "origin/main")
        ),
        adr_contents=load_reference_contents(engine.repo, records),
    )
    return any(
        plan.feature_id == run["feature_id"] and plan.scope_digest == run["scope_digest"]
        for plan in plans.ready
    )
