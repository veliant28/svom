from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import modes, prefilters
from .options import normalize_options
from .types import CommandOutput


def run_category_mapping_command(*, raw_options: Mapping[str, Any], output: CommandOutput) -> None:
    options = normalize_options(raw_options)
    queryset = prefilters.build_base_queryset(supplier_codes=options.supplier_codes)

    if options.recheck_risky_mappings:
        modes.run_risky_recheck(queryset=queryset, options=options, output=output)
        return

    if options.has_selective_guardrail_recheck:
        modes.run_selective_guardrail_recheck(queryset=queryset, options=options, output=output)
        return

    modes.run_auto_map(queryset=queryset, options=options, output=output)
