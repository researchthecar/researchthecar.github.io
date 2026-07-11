from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from rtc_pipeline.batch import run_pilot
from rtc_pipeline.inventory import find_vehicle, load_inventory
from rtc_pipeline.models import Vehicle
from rtc_pipeline.nhtsa import fetch_and_cache, refetch_and_cache
from rtc_pipeline.normalize import normalize_to_file
from rtc_pipeline.quality import build_quality_report, build_source_failure_report
from rtc_pipeline.registry import build_registry
from rtc_pipeline.render import render_normalized_file
from rtc_pipeline.synthesis import render_synthesis_markdown, render_synthesis_reports, synthesize_file, synthesize_ready_group
from rtc_pipeline.validate import validate_normalized_file


def resolve_vehicle(args: argparse.Namespace) -> Vehicle:
    if args.inventory:
        vehicle = find_vehicle(load_inventory(Path(args.inventory)), args.year, args.make, args.model)
        if vehicle:
            return vehicle
        raise SystemExit(f"Vehicle not found in inventory: {args.year} {args.make} {args.model}")
    return Vehicle(year=args.year, make=args.make, model=args.model)


def add_vehicle_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--make", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--inventory", default="data/vehicle_registry.json")


def cmd_ingest(args: argparse.Namespace) -> int:
    vehicle = resolve_vehicle(args)
    for source_type in args.sources:
        if args.refresh:
            path = refetch_and_cache(vehicle, source_type)
        else:
            path = fetch_and_cache(vehicle, source_type)
        print(path)
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    vehicle = resolve_vehicle(args)
    print(normalize_to_file(vehicle))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_normalized_file(Path(args.input))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.input}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    print(render_normalized_file(Path(args.input)))
    return 0


def cmd_run_vehicle(args: argparse.Namespace) -> int:
    vehicle = resolve_vehicle(args)
    if not args.skip_ingest:
        for source_type in args.sources:
            if args.refresh:
                print(refetch_and_cache(vehicle, source_type))
            else:
                print(fetch_and_cache(vehicle, source_type))
    normalized_path = normalize_to_file(vehicle)
    print(normalized_path)
    errors = validate_normalized_file(normalized_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(render_normalized_file(normalized_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research the Car reprocessing pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest-nhtsa", help="Fetch and cache NHTSA raw records")
    add_vehicle_args(ingest)
    ingest.add_argument("--sources", nargs="+", choices=["recalls", "complaints"], default=["recalls", "complaints"])
    ingest.add_argument("--refresh", action="store_true", help="Refetch even when a local raw cache exists")
    ingest.set_defaults(func=cmd_ingest)

    normalize = subparsers.add_parser("normalize", help="Normalize cached evidence for one vehicle")
    add_vehicle_args(normalize)
    normalize.set_defaults(func=cmd_normalize)

    validate = subparsers.add_parser("validate", help="Validate a normalized vehicle evidence file")
    validate.add_argument("input")
    validate.set_defaults(func=cmd_validate)

    render = subparsers.add_parser("render", help="Render a normalized vehicle evidence file to Markdown")
    render.add_argument("input")
    render.set_defaults(func=cmd_render)

    run_vehicle = subparsers.add_parser("run-vehicle", help="Ingest, normalize, validate, and render one vehicle")
    add_vehicle_args(run_vehicle)
    run_vehicle.add_argument("--skip-ingest", action="store_true")
    run_vehicle.add_argument("--refresh", action="store_true", help="Refetch even when a local raw cache exists")
    run_vehicle.add_argument("--sources", nargs="+", choices=["recalls", "complaints"], default=["recalls", "complaints"])
    run_vehicle.set_defaults(func=cmd_run_vehicle)

    run_pilot_parser = subparsers.add_parser("run-pilot", help="Run the pilot manifest batch")
    run_pilot_parser.add_argument("--manifest", default="data/pilot_vehicles.json")
    run_pilot_parser.add_argument("--inventory", default="data/vehicle_registry.json")
    run_pilot_parser.add_argument("--summary", default="data/rendered/pilot_summary.json")
    run_pilot_parser.add_argument("--skip-ingest", action="store_true")
    run_pilot_parser.add_argument("--refresh", action="store_true", help="Refetch even when local raw caches exist")
    run_pilot_parser.add_argument("--limit", type=int)
    run_pilot_parser.add_argument("--quiet", action="store_true")
    run_pilot_parser.add_argument("--strict-sources", action="store_true", help="Exit non-zero when any source fetch fails")
    run_pilot_parser.add_argument("--sources", nargs="+", choices=["recalls", "complaints"], default=["recalls", "complaints"])
    run_pilot_parser.set_defaults(func=cmd_run_pilot)

    build_registry_parser = subparsers.add_parser("build-registry", help="Build canonical vehicle registry from legacy inventory")
    build_registry_parser.add_argument("--inventory", default="assets/cars_parsed.json")
    build_registry_parser.add_argument("--output", default="data/vehicle_registry.json")
    build_registry_parser.set_defaults(func=cmd_build_registry)

    source_failures = subparsers.add_parser("report-source-failures", help="Write a source failure report from a batch summary")
    source_failures.add_argument("--summary", default="data/rendered/pilot_summary.json")
    source_failures.add_argument("--output", default="data/rendered/source_failures.json")
    source_failures.set_defaults(func=cmd_report_source_failures)

    quality = subparsers.add_parser("report-quality", help="Write a readiness/quality report for normalized vehicles")
    quality.add_argument("--normalized-glob", default="data/normalized/vehicles/*.json")
    quality.add_argument("--summary", default="data/rendered/pilot_summary.json")
    quality.add_argument("--output", default="data/rendered/pilot_quality_report.json")
    quality.set_defaults(func=cmd_report_quality)

    synthesize = subparsers.add_parser("synthesize", help="Synthesize structured reports from ready normalized evidence")
    synthesize.add_argument("--quality", default="data/rendered/pilot_quality_report.json")
    synthesize.add_argument("--input", help="Synthesize a single normalized vehicle JSON file")
    synthesize.add_argument("--provider", choices=["draft", "gemini"], default="draft")
    synthesize.add_argument("--limit", type=int)
    synthesize.set_defaults(func=cmd_synthesize)

    render_synthesis = subparsers.add_parser("render-synthesis", help="Render synthesis report JSON to Markdown")
    render_synthesis.add_argument("input", nargs="?")
    render_synthesis.add_argument("--glob", default="data/reports/*.json")
    render_synthesis.set_defaults(func=cmd_render_synthesis)

    return parser


def cmd_run_pilot(args: argparse.Namespace) -> int:
    summary = run_pilot(
        manifest_path=Path(args.manifest),
        inventory_path=Path(args.inventory),
        summary_path=Path(args.summary),
        sources=args.sources,
        skip_ingest=args.skip_ingest,
        refresh=args.refresh,
        limit=args.limit,
        progress=not args.quiet,
    )
    print(json.dumps({"summary": args.summary, "status_counts": summary["status_counts"]}, indent=2, sort_keys=True))
    allowed = {"ok"} if args.strict_sources else {"ok", "source_error"}
    return 0 if set(summary["status_counts"]) <= allowed else 1


def cmd_build_registry(args: argparse.Namespace) -> int:
    print(build_registry(Path(args.inventory), Path(args.output)))
    return 0


def cmd_report_source_failures(args: argparse.Namespace) -> int:
    report = build_source_failure_report(Path(args.summary), Path(args.output))
    print(json.dumps({"output": args.output, "failure_count": report["failure_count"]}, indent=2, sort_keys=True))
    return 0


def cmd_report_quality(args: argparse.Namespace) -> int:
    report = build_quality_report(args.normalized_glob, Path(args.summary), Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "vehicle_count": report["vehicle_count"],
                "status_counts": report["status_counts"],
                "flag_counts": report["flag_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    if args.input:
        paths = [synthesize_file(Path(args.input), provider_name=args.provider)]
    else:
        paths = synthesize_ready_group(Path(args.quality), provider_name=args.provider, limit=args.limit)
    print(json.dumps({"provider": args.provider, "count": len(paths), "outputs": [str(path) for path in paths]}, indent=2))
    return 0


def cmd_render_synthesis(args: argparse.Namespace) -> int:
    if args.input:
        print(render_synthesis_markdown(Path(args.input)))
    else:
        paths = render_synthesis_reports(args.glob)
        print(json.dumps({"count": len(paths), "outputs": [str(path) for path in paths]}, indent=2))
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
