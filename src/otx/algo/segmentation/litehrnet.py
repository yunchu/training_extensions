# Copyright (C) 2023 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""LiteHRNet model implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from torch.onnx import OperatorExportTypes

from otx.algo.utils.mmconfig import read_mmconfig
from otx.algo.utils.support_otx_v1 import OTXv1Helper
from otx.core.exporter.base import OTXModelExporter
from otx.core.exporter.native import OTXNativeModelExporter
from otx.core.metrics.dice import SegmCallable
from otx.core.model.base import DefaultOptimizerCallable, DefaultSchedulerCallable
from otx.core.model.segmentation import MMSegCompatibleModel
from otx.core.schedulers import LRSchedulerListCallable
from otx.core.types.label import LabelInfoTypes
from otx.core.utils.utils import get_mean_std_from_data_processing

if TYPE_CHECKING:
    from lightning.pytorch.cli import LRSchedulerCallable, OptimizerCallable

    from otx.core.metrics import MetricCallable


class LiteHRNet(MMSegCompatibleModel):
    """LiteHRNet Model."""

    def __init__(
        self,
        label_info: LabelInfoTypes,
        variant: Literal["18", 18, "s", "x"],
        optimizer: OptimizerCallable = DefaultOptimizerCallable,
        scheduler: LRSchedulerCallable | LRSchedulerListCallable = DefaultSchedulerCallable,
        metric: MetricCallable = SegmCallable,  # type: ignore[assignment]
        torch_compile: bool = False,
    ) -> None:
        self.model_name = f"litehrnet_{variant}"
        config = read_mmconfig(model_name=self.model_name)
        super().__init__(
            label_info=label_info,
            config=config,
            optimizer=optimizer,
            scheduler=scheduler,
            metric=metric,
            torch_compile=torch_compile,
        )

    @property
    def _exporter(self) -> OTXModelExporter:
        """Creates OTXModelExporter object that can export the model."""
        mean, std = get_mean_std_from_data_processing(self.config)

        return OTXNativeModelExporter(
            task_level_export_parameters=self._export_parameters,
            input_size=self.image_size,
            mean=mean,
            std=std,
            resize_mode="standard",
            pad_value=0,
            swap_rgb=False,
            via_onnx=True,
            onnx_export_configuration={"operator_export_type": OperatorExportTypes.ONNX_ATEN_FALLBACK},
            output_names=None,
        )

    def load_from_otx_v1_ckpt(self, state_dict: dict, add_prefix: str = "model.model.") -> dict:
        """Load the previous OTX ckpt according to OTX2.0."""
        return OTXv1Helper.load_seg_lite_hrnet_ckpt(state_dict, add_prefix)

    @property
    def _optimization_config(self) -> dict[str, Any]:
        """PTQ config for LiteHRNet."""
        # TODO(Kirill): check PTQ without adding the whole backbone to ignored_scope
        ignored_scope = self._obtain_ignored_scope()
        optim_config = {
            "advanced_parameters": {
                "activations_range_estimator_params": {
                    "min": {"statistics_type": "QUANTILE", "aggregator_type": "MIN", "quantile_outlier_prob": 1e-4},
                    "max": {"statistics_type": "QUANTILE", "aggregator_type": "MAX", "quantile_outlier_prob": 1e-4},
                },
            },
        }
        optim_config.update(ignored_scope)
        return optim_config

    def _obtain_ignored_scope(self) -> dict[str, Any]:
        """Returns the ignored scope for the model based on the litehrnet version."""
        if self.model_name == "litehrnet_18":
            ignored_scope_names = [
                "/model/backbone/stage0/stage0.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.0/Add_1",
                "/model/backbone/stage0/stage0.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.1/Add_1",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.0/Add_1",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.0/Add_2",
                "/model/backbone/stage1/stage1.0/Add_5",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.1/Add_1",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.1/Add_2",
                "/model/backbone/stage1/stage1.1/Add_5",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.2/Add_1",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.2/Add_2",
                "/model/backbone/stage1/stage1.2/Add_5",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.3/Add_1",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.3/Add_2",
                "/model/backbone/stage1/stage1.3/Add_5",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.0/Add_1",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.0/Add_2",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.0/Add_3",
                "/model/backbone/stage2/stage2.0/Add_6",
                "/model/backbone/stage2/stage2.0/Add_7",
                "/model/backbone/stage2/stage2.0/Add_11",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.1/Add_1",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.1/Add_2",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.1/Add_3",
                "/model/backbone/stage2/stage2.1/Add_6",
                "/model/backbone/stage2/stage2.1/Add_7",
                "/model/backbone/stage2/stage2.1/Add_11",
                "/model/aggregator/Add",
                "/model/aggregator/Add_1",
                "/model/aggregator/Add_2",
                "/model/backbone/stage2/stage2.1/Add",
            ]

            return {
                "ignored_scope": {
                    "patterns": ["/model/backbone/*"],
                    "names": ignored_scope_names,
                },
                "preset": "mixed",
            }

        if self.model_name == "litehrnet_s":
            ignored_scope_names = [
                "/model/backbone/stage0/stage0.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.0/Add_1",
                "/model/backbone/stage0/stage0.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.1/Add_1",
                "/model/backbone/stage0/stage0.2/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.2/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.2/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.2/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.2/Add_1",
                "/model/backbone/stage0/stage0.3/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.3/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.3/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.3/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.3/Add_1",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.0/Add_1",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.0/Add_2",
                "/model/backbone/stage1/stage1.0/Add_5",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.1/Add_1",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.1/Add_2",
                "/model/backbone/stage1/stage1.1/Add_5",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.2/Add_1",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.2/Add_2",
                "/model/backbone/stage1/stage1.2/Add_5",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.3/Add_1",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.3/Add_2",
                "/model/backbone/stage1/stage1.3/Add_5",
                "/model/aggregator/Add",
                "/model/aggregator/Add_1",
            ]

            return {
                "ignored_scope": {
                    "names": ignored_scope_names,
                },
                "preset": "mixed",
            }

        if self.model_name == "litehrnet_x":
            ignored_scope_names = [
                "/model/backbone/stage0/stage0.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.0/Add_1",
                "/model/backbone/stage0/stage0.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage0/stage0.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage0/stage0.1/Add_1",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.0/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.0/Add_1",
                "/model/backbone/stage1/stage1.0/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.0/Add_2",
                "/model/backbone/stage1/stage1.0/Add_5",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.1/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.1/Add_1",
                "/model/backbone/stage1/stage1.1/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.1/Add_2",
                "/model/backbone/stage1/stage1.1/Add_5",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.2/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.2/Add_1",
                "/model/backbone/stage1/stage1.2/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.2/Add_2",
                "/model/backbone/stage1/stage1.2/Add_5",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.3/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage1/stage1.3/Add_1",
                "/model/backbone/stage1/stage1.3/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage1/stage1.3/Add_2",
                "/model/backbone/stage1/stage1.3/Add_5",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.0/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.0/Add_1",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.0/Add_2",
                "/model/backbone/stage2/stage2.0/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.0/Add_3",
                "/model/backbone/stage2/stage2.0/Add_6",
                "/model/backbone/stage2/stage2.0/Add_7",
                "/model/backbone/stage2/stage2.0/Add_11",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.1/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.1/Add_1",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.1/Add_2",
                "/model/backbone/stage2/stage2.1/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.1/Add_3",
                "/model/backbone/stage2/stage2.1/Add_6",
                "/model/backbone/stage2/stage2.1/Add_7",
                "/model/backbone/stage2/stage2.1/Add_11",
                "/model/backbone/stage2/stage2.2/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.2/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.2/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.2/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.2/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.2/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.2/Add_1",
                "/model/backbone/stage2/stage2.2/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.2/Add_2",
                "/model/backbone/stage2/stage2.2/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.2/Add_3",
                "/model/backbone/stage2/stage2.2/Add_6",
                "/model/backbone/stage2/stage2.2/Add_7",
                "/model/backbone/stage2/stage2.2/Add_11",
                "/model/backbone/stage2/stage2.3/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.3/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.3/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.3/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.3/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage2/stage2.3/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage2/stage2.3/Add_1",
                "/model/backbone/stage2/stage2.3/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage2/stage2.3/Add_2",
                "/model/backbone/stage2/stage2.3/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage2/stage2.3/Add_3",
                "/model/backbone/stage2/stage2.3/Add_6",
                "/model/backbone/stage2/stage2.3/Add_7",
                "/model/backbone/stage2/stage2.3/Add_11",
                "/model/backbone/stage3/stage3.0/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage3/stage3.0/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage3/stage3.0/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage3/stage3.0/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage3/stage3.0/layers/layers.0/cross_resolution_weighting/Mul_4",
                "/model/backbone/stage3/stage3.0/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage3/stage3.0/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage3/stage3.0/Add_1",
                "/model/backbone/stage3/stage3.0/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage3/stage3.0/Add_2",
                "/model/backbone/stage3/stage3.0/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage3/stage3.0/Add_3",
                "/model/backbone/stage3/stage3.0/layers/layers.1/cross_resolution_weighting/Mul_4",
                "/model/backbone/stage3/stage3.0/Add_4",
                "/model/backbone/stage3/stage3.0/Add_7",
                "/model/backbone/stage3/stage3.0/Add_8",
                "/model/backbone/stage3/stage3.0/Add_9",
                "/model/backbone/stage3/stage3.0/Add_13",
                "/model/backbone/stage3/stage3.0/Add_14",
                "/model/backbone/stage3/stage3.0/Add_19",
                "/model/backbone/stage3/stage3.1/layers/layers.0/cross_resolution_weighting/Mul",
                "/model/backbone/stage3/stage3.1/layers/layers.0/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage3/stage3.1/layers/layers.0/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage3/stage3.1/layers/layers.0/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage3/stage3.1/layers/layers.0/cross_resolution_weighting/Mul_4",
                "/model/backbone/stage3/stage3.1/layers/layers.1/cross_resolution_weighting/Mul",
                "/model/backbone/stage3/stage3.1/layers/layers.1/cross_resolution_weighting/Mul_1",
                "/model/backbone/stage3/stage3.1/Add_1",
                "/model/backbone/stage3/stage3.1/layers/layers.1/cross_resolution_weighting/Mul_2",
                "/model/backbone/stage3/stage3.1/Add_2",
                "/model/backbone/stage3/stage3.1/layers/layers.1/cross_resolution_weighting/Mul_3",
                "/model/backbone/stage3/stage3.1/Add_3",
                "/model/backbone/stage3/stage3.1/layers/layers.1/cross_resolution_weighting/Mul_4",
                "/model/backbone/stage3/stage3.1/Add_4",
                "/model/backbone/stage3/stage3.1/Add_7",
                "/model/backbone/stage3/stage3.1/Add_8",
                "/model/backbone/stage3/stage3.1/Add_9",
                "/model/backbone/stage3/stage3.1/Add_13",
                "/model/backbone/stage3/stage3.1/Add_14",
                "/model/backbone/stage3/stage3.1/Add_19",
                "/model/backbone/stage0/stage0.0/Add",
                "/model/backbone/stage0/stage0.1/Add",
                "/model/backbone/stage1/stage1.0/Add",
                "/model/backbone/stage1/stage1.1/Add",
                "/model/backbone/stage1/stage1.2/Add",
                "/model/backbone/stage1/stage1.3/Add",
                "/model/backbone/stage2/stage2.0/Add",
                "/model/backbone/stage2/stage2.1/Add",
                "/model/backbone/stage2/stage2.2/Add",
                "/model/backbone/stage2/stage2.3/Add",
                "/model/backbone/stage3/stage3.0/Add",
                "/model/backbone/stage3/stage3.1/Add",
            ]

            return {
                "ignored_scope": {
                    "patterns": ["/model/aggregator/*"],
                    "names": ignored_scope_names,
                },
                "preset": "performance",
            }

        return {}
