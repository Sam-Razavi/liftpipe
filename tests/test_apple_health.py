import subprocess
import sys
import textwrap
import zipfile
from datetime import date
from pathlib import Path

import pytest

from liftpipe.config import Settings
from liftpipe.ingest.apple_health import AppleHealthFormatError, parse_apple_health
from liftpipe.ingest.pipeline import ingest_apple_health
from liftpipe.ingest.raw_store import connect

EXPORT = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE HealthData [
<!ELEMENT HealthData (ExportDate,Me,(Record|Workout)*)>
]>
<HealthData locale="en_SE">
 <ExportDate value="2026-03-01 21:00:00 +0100"/>
 <Me HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexFemale"/>
 <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Withings" unit="kg"
   creationDate="2026-02-01 07:05:00 +0100" startDate="2026-02-01 07:05:00 +0100"
   endDate="2026-02-01 07:05:00 +0100" value="71.4"/>
 <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Withings" unit="kg"
   creationDate="2026-02-01 07:05:00 +0100" startDate="2026-02-01 07:05:00 +0100"
   endDate="2026-02-01 07:05:00 +0100" value="71.4"/>
 <Record type="HKQuantityTypeIdentifierBodyFatPercentage" sourceName="Withings" unit="%"
   startDate="2026-02-01 07:05:00 +0100" endDate="2026-02-01 07:05:00 +0100" value="0.241"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" unit="count/min"
   startDate="2026-02-01 07:05:00 +0100" endDate="2026-02-01 07:05:00 +0100" value="61">
  <MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="0"/>
 </Record>
 <Workout workoutActivityType="HKWorkoutActivityTypeTraditionalStrengthTraining"
   duration="3000" durationUnit="s" totalEnergyBurned="1250" totalEnergyBurnedUnit="kJ"
   sourceName="Watch" startDate="2026-02-02 18:00:00 +0100" endDate="2026-02-02 18:50:00 +0100"/>
 <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min"
   sourceName="Watch" startDate="2026-06-02 18:00:00 +0200" endDate="2026-06-02 18:30:00 +0200">
  <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="320" unit="kcal"/>
  <WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning" sum="3.1"
    unit="mi"/>
 </Workout>
</HealthData>
"""


@pytest.fixture
def export_xml(tmp_path: Path) -> Path:
    path = tmp_path / "export.xml"
    path.write_text(EXPORT)
    return path


def test_keeps_body_records_only_and_dedupes(export_xml: Path) -> None:
    frames = parse_apple_health(export_xml)
    assert sorted(frames.records["record_type"].to_list()) == [
        "HKQuantityTypeIdentifierBodyFatPercentage",
        "HKQuantityTypeIdentifierBodyMass",
    ]
    mass = frames.records.row(1, named=True)
    assert mass["value"] == 71.4
    assert mass["start_date"].isoformat() == "2026-02-01T07:05:00"
    assert mass["utc_offset"] == "+0100"


def test_workouts_from_attributes_and_statistics(export_xml: Path) -> None:
    w = parse_apple_health(export_xml).workouts.rows(named=True)
    strength, run = w
    assert strength["duration_min"] == pytest.approx(50)
    assert strength["total_energy_kcal"] == pytest.approx(298.76, abs=0.01)  # 1250 kJ
    assert run["total_energy_kcal"] == 320
    assert run["total_distance_km"] == pytest.approx(4.989, abs=0.001)  # 3.1 mi
    assert run["utc_offset"] == "+0200"


def test_reads_zip_archive(export_xml: Path, tmp_path: Path) -> None:
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(export_xml, "apple_health_export/export.xml")
        zf.writestr("apple_health_export/export_cda.xml", "<ClinicalDocument/>")
    frames = parse_apple_health(archive)
    assert frames.records.height == 2
    assert frames.workouts.height == 2


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("<HealthData><Record type='x'", "malformed XML"),
        (EXPORT.replace("2026-02-01 07:05:00 +0100", "01/02/2026"), "timestamp"),
    ],
)
def test_rejects_broken_exports(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "export.xml"
    path.write_text(content)
    with pytest.raises(AppleHealthFormatError, match=message):
        parse_apple_health(path)


def test_ingest_overlapping_exports(settings: Settings) -> None:
    con = connect(settings.warehouse_path)
    results = ingest_apple_health(settings, con)
    older_records, _, newer_records, _ = results
    assert newer_records.new_rows < newer_records.rows_in_file
    total = con.execute("SELECT count(*) FROM raw.health_records").fetchone()[0]
    assert total == newer_records.rows_in_file
    assert all(r.skipped for r in ingest_apple_health(settings, con))
    assert older_records.rows_in_file > 0


def test_streaming_parse_uses_bounded_memory(tmp_path: Path) -> None:
    """Parsing a ~100 MB export must not load the tree: peak RSS stays far below a DOM."""
    from liftpipe.synthetic.apple_health import write_apple_health_xml
    from liftpipe.synthetic.hevy import generate_sessions

    start, end = date(2025, 1, 1), date(2025, 12, 31)
    path = tmp_path / "export.xml"
    with path.open("w") as fh:
        write_apple_health_xml(fh, generate_sessions(1, start, end), 1, start, end, 1000)
    size_mb = path.stat().st_size / 1e6
    assert size_mb > 80

    script = textwrap.dedent(
        f"""
        import resource, sys
        from pathlib import Path
        from liftpipe.ingest.apple_health import parse_apple_health
        baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        frames = parse_apple_health(Path({str(path)!r}))
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(frames.records.height, (peak - baseline) / 1024)
        """
    )
    out = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    ).stdout.split()
    records, growth_mb = int(out[0]), float(out[1])
    assert records > 300
    # A full lxml tree of this file needs several times its size; streaming stays small.
    assert growth_mb < size_mb / 2, f"RSS grew {growth_mb:.0f} MB on a {size_mb:.0f} MB file"
