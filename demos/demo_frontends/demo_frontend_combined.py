"""Render four Combined-frontend variants, then run Vitis HLS C synthesis.

Each variant applies both stages: the Jinja stage picks `vector_size`,
`scale`, and `lanes` (structural parameterization, same as the Jinja demo),
and the defines stage optionally sets `USE_SATURATE` (macro-level
parameterization, same as the define demo) to switch the generated design
between plain and saturating addition.
"""

import argparse
from pathlib import Path
from tempfile import mkdtemp

from hlsfactory.combined_frontend import CombinedFrontend
from hlsfactory.flow_vitis import VitisHLSSynthFlow
from hlsfactory.framework import Design

CONFIGURATIONS = [
    {"jinja": {"vector_size": 16, "scale": 2, "lanes": 1}, "defines": {}},
    {
        "jinja": {"vector_size": 16, "scale": 4, "lanes": 2},
        "defines": {"USE_SATURATE": None},
    },
    {"jinja": {"vector_size": 32, "scale": 2, "lanes": 1}, "defines": {}},
    {
        "jinja": {"vector_size": 32, "scale": 4, "lanes": 4},
        "defines": {"USE_SATURATE": None},
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Output directory (default: a new temporary directory).",
    )
    parser.add_argument(
        "--vitis-hls-bin", help="Vitis HLS executable (default: vitis_hls on PATH)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Synthesis timeout per design in seconds.",
    )
    args = parser.parse_args()

    work_dir = args.work_dir or Path(mkdtemp(prefix="hlsfactory-demo-combined-"))
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"Work directory: {work_dir}", flush=True)

    # Copy the parameterized source so generated files stay in the work directory.
    source_dir = Path(__file__).resolve().parent / "designs" / "design_combined"
    design = Design.from_dir_with_config(source_dir)
    design.copy_to_new_parent_dir(work_dir)

    frontend = CombinedFrontend(work_dir=work_dir, configs=CONFIGURATIONS)
    variants = frontend.execute(design)

    synth_flow = VitisHLSSynthFlow(vitis_hls_bin=args.vitis_hls_bin, log_output=True)
    completed = []
    for config, variant in zip(CONFIGURATIONS, variants, strict=True):
        print(f"Synthesizing {config}: {variant.dir}", flush=True)
        completed.extend(synth_flow.execute(variant, timeout=args.timeout))

    if len(completed) != len(CONFIGURATIONS):
        raise RuntimeError(
            f"Only {len(completed)}/4 variants synthesized; inspect logs in {work_dir}."
        )
    print(f"Synthesized all four variants. Reports and data_hls.json files: {work_dir}")


if __name__ == "__main__":
    main()
