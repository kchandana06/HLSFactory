"""Frontend that combines Jinja templating with C++ preprocessor macro expansion.

Each design variant can apply either stage, both, or neither:

- ``"jinja"``: rendered first, same semantics as :class:`JinjaFrontend
  <hlsfactory.jinja_frontend.JinjaFrontend>` -- every ``*.jinja`` file under
  the design is rendered with the given context dict and the ``.jinja``
  suffix is dropped.
- ``"defines"``: applied second, to the design as it stands after the Jinja
  stage (if any), same semantics as :class:`CPPPreprocessorFrontend
  <hlsfactory.define_frontend.CPPPreprocessorFrontend>` -- every C/C++
  source file in the design is rewritten in place by the preprocessor using
  ``-D`` flags built from the given dict.

This lets one design use Jinja for structural parameterization (loops,
conditional branches, pragma generation) and preprocessor macros for
lightweight value substitution or conditional compilation, in a single pass.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from hlsfactory.define_frontend import run_cpp_preprocessor
from hlsfactory.framework import Design, Frontend
from hlsfactory.jinja_frontend import render_jinja_files
from hlsfactory.utils import (
    ExecutionDataStatus,
    update_execution_data_with_flow_results,
)


class CombinedFrontend(Frontend):
    """Frontend that applies Jinja templating and/or C++ preprocessor defines.

    Each entry in ``configs`` is a dict with two optional keys:

    - ``"jinja"``: a dict passed as the Jinja render context. If the key is
      present (even as ``{}``), every ``*.jinja`` file in the design is
      rendered. Omit the key to skip the Jinja stage entirely.
    - ``"defines"``: a dict of preprocessor macro definitions, passed as
      ``-D`` flags. If the key is present (even as ``{}``), every C/C++
      source file in the design is run through the preprocessor. Omit the
      key to skip the preprocessor stage entirely.

    A config must include at least one of the two keys. A config with both
    keys renders the Jinja templates first, then runs the preprocessor over
    the resulting (and any pre-existing) C/C++ sources.
    """

    name = "CombinedFrontend"

    def __init__(
        self,
        work_dir: Path,
        configs: list[dict[str, Any]],
        log_execution_time: bool = True,
    ) -> None:
        self.work_dir = work_dir
        self.configs = configs
        self.log_execution_time = log_execution_time

    def load_configs_from_jsonl(self, fp_jsonl: Path):
        configs = []
        txt_config = fp_jsonl.read_text()
        lines = txt_config.splitlines()
        for line in lines:
            config = json.loads(line.strip())
            configs.append(config)
        self.configs = configs
        return self.configs

    def load_configs_from_json(self, fp_json: Path):
        txt_json = fp_json.read_text()
        config_list = json.loads(txt_json)
        if not isinstance(config_list, list):
            raise ValueError("Configs must be a list of dicts")
        for item in config_list:
            if not isinstance(item, dict):
                raise ValueError("List items must be dicts")
            self.configs.append(item)
        return self.configs

    def execute(self, design: Design, timeout: float | None = None) -> list[Design]:
        t_0 = time.perf_counter()

        new_designs = []

        for config in self.configs:
            jinja_context = config.get("jinja")
            defines = config.get("defines")
            if jinja_context is None and defines is None:
                raise ValueError(
                    "Each config needs at least a 'jinja' or 'defines' key: "
                    f"got {config!r}"
                )

            config_hash = hashlib.md5(  # noqa: S324
                string=str(config).encode(),
            ).hexdigest()

            new_design = design.copy_and_rename_to_new_parent_dir(
                f"{design.name}__combined_{config_hash}",
                design.dir.parent,
            )
            new_designs.append(new_design)

            if jinja_context is not None:
                render_jinja_files(new_design.dir, jinja_context)

            if defines is not None:
                run_cpp_preprocessor(new_design.dir, defines)

        t_1 = time.perf_counter()

        update_execution_data_with_flow_results(
            new_design.dir, self.name, ExecutionDataStatus.SUCCESS, t_0, t_1
        )
        update_execution_data_with_flow_results(
            design.dir, self.name, ExecutionDataStatus.SUCCESS, t_0, t_1
        )

        return new_designs
