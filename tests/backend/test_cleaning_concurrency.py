from baseera.ingestion import ArtifactStore
from baseera.models import Dataset, DatasetVersion
from fastapi.testclient import TestClient


def test_losing_cleaning_publish_cannot_overwrite_the_winning_artifact(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
):
    uploaded = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("race.csv", b"id,revenue\n001,100\n", "text/csv")},
        headers=auth_headers,
    ).json()
    dataset_id = uploaded["dataset"]["id"]
    source_id = uploaded["version"]["id"]
    winner_id = "dataset-version-concurrent-winner"
    winner_key = f"tenant-demo/datasets/{dataset_id}/versions/2.json"
    winner_rows = [{"id": "001", "revenue": 777}]
    write_rows = ArtifactStore.write_rows
    interleaved = False

    def publish_competitor_before_this_write(store, object_key, rows):
        nonlocal interleaved
        assert not interleaved, "The hook must publish one competing transaction only"
        interleaved = True
        # Deterministically insert the competing commit between next-version selection and
        # artifact publication. An existing legacy numeric path must also remain protected.
        write_rows(store, winner_key, winner_rows)
        with client.app.state.session_factory() as db:
            source = db.get(DatasetVersion, source_id)
            db.add(
                DatasetVersion(
                    id=winner_id,
                    organization_id=source.organization_id,
                    dataset_id=dataset_id,
                    version_number=2,
                    parent_version_id=source_id,
                    kind="cleaned",
                    data_object_key=winner_key,
                    row_count=1,
                    columns=source.columns,
                    coverage=source.coverage,
                    extraction=source.extraction,
                    created_by=source.created_by,
                )
            )
            db.flush()
            db.get(Dataset, dataset_id).published_version_id = winner_id
            db.commit()
        write_rows(store, object_key, rows)

    monkeypatch.setattr(ArtifactStore, "write_rows", publish_competitor_before_this_write)
    losing_request = client.post(
        f"/api/v1/dataset-versions/{source_id}/cleaning/apply",
        json={
            "steps": [{"kind": "trim_whitespace", "columns": ["id"]}],
            "expected_version": 1,
            "approved": True,
        },
        headers=auth_headers,
    )
    assert interleaved
    assert losing_request.status_code == 409
    assert losing_request.json()["error"]["code"] == "version_conflict"
    dataset = client.get(f"/api/v1/datasets/{dataset_id}").json()
    assert dataset["published_version_id"] == winner_id
    metric = client.post(
        "/api/v1/metrics/query",
        json={"dataset_version_id": winner_id, "metric_id": "net_revenue"},
        headers=auth_headers,
    )
    assert metric.status_code == 200
    assert metric.json()["value"] == 777
    original = client.post(
        "/api/v1/metrics/query",
        json={"dataset_version_id": source_id, "metric_id": "net_revenue"},
        headers=auth_headers,
    )
    assert original.json()["value"] == 100
