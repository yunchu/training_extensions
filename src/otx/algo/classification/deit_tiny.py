# Copyright (C) 2023 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""DeitTiny model implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import torch
from mmpretrain.models.utils import resize_pos_embed

from otx.algo.explain.explain_algo import ViTReciproCAM
from otx.algo.utils.mmconfig import read_mmconfig
from otx.algo.utils.support_otx_v1 import OTXv1Helper
from otx.core.metrics.accuracy import HLabelClsMetricCallble, MultiClassClsMetricCallable, MultiLabelClsMetricCallable
from otx.core.model.base import DefaultOptimizerCallable, DefaultSchedulerCallable
from otx.core.model.classification import (
    MMPretrainHlabelClsModel,
    MMPretrainMulticlassClsModel,
    MMPretrainMultilabelClsModel,
)
from otx.core.model.utils.mmpretrain import ExplainableMixInMMPretrainModel
from otx.core.schedulers import LRSchedulerListCallable
from otx.core.types.label import HLabelInfo, LabelInfoTypes

if TYPE_CHECKING:
    from lightning.pytorch.cli import LRSchedulerCallable, OptimizerCallable
    from mmpretrain.models.classifiers import ImageClassifier
    from mmpretrain.structures import DataSample

    from otx.core.metrics import MetricCallable


class ForwardExplainMixInForDeit(ExplainableMixInMMPretrainModel):
    """Deit model which can attach a XAI (Explainable AI) branch."""

    @torch.no_grad()
    def head_forward_fn(self, x: torch.Tensor) -> torch.Tensor:
        """Performs model's neck and head forward."""
        if not hasattr(self.model.backbone, "layers"):
            raise ValueError
        if not hasattr(self.model.backbone, "final_norm"):
            raise ValueError
        if not hasattr(self.model, "with_neck"):
            raise ValueError

        # Part of the last transformer_encoder block (except first LayerNorm)
        target_layer = self.model.backbone.layers[-1]
        x = x + target_layer.attn(x)
        x = target_layer.ffn(target_layer.norm2(x), identity=x)

        # Final LayerNorm and neck
        if self.model.backbone.final_norm:
            x = self.model.backbone.norm1(x)
        if self.model.with_neck:
            x = self.model.neck(x)

        # Head
        cls_token = x[:, 0]
        layer_output = [None, cls_token]
        logit = self.model.head.forward(layer_output)
        if isinstance(logit, list):
            logit = torch.from_numpy(np.array(logit))
        return logit

    @staticmethod
    def _forward_explain_image_classifier(
        self: ImageClassifier,
        inputs: torch.Tensor,
        data_samples: list[DataSample] | None = None,
        mode: str = "tensor",
    ) -> dict:
        """Forward func of the ImageClassifier instance, which located in is in OTXModel().model."""
        backbone = self.backbone

        ### Start of backbone forward
        batch_size = inputs.shape[0]
        x, patch_resolution = backbone.patch_embed(inputs)

        if backbone.cls_token is not None:
            cls_token = backbone.cls_token.expand(batch_size, -1, -1)
            x = torch.cat((cls_token, x), dim=1)

        x = x + resize_pos_embed(
            backbone.pos_embed,
            backbone.patch_resolution,
            patch_resolution,
            mode=backbone.interpolate_mode,
            num_extra_tokens=backbone.num_extra_tokens,
        )
        x = backbone.drop_after_pos(x)

        x = backbone.pre_norm(x)

        outs = []
        layernorm_feat = None
        for i, layer in enumerate(backbone.layers):
            if i == len(backbone.layers) - 1:
                layernorm_feat = layer.norm1(x)

            x = layer(x)

            if i == len(backbone.layers) - 1 and backbone.final_norm:
                x = backbone.ln1(x)

            if i in backbone.out_indices:
                outs.append(backbone._format_output(x, patch_resolution))  # noqa: SLF001

        x = tuple(outs)
        ### End of backbone forward

        saliency_map = self.explain_fn(layernorm_feat)

        if self.with_neck:
            x = self.neck(x)

        feature_vector = x[-1]

        if mode == "tensor":
            logits = self.head(x) if self.with_head else x
        elif mode == "predict":
            logits = self.head.predict(x, data_samples)
        else:
            msg = f'Invalid mode "{mode}".'
            raise RuntimeError(msg)

        return {
            "logits": logits,
            "feature_vector": feature_vector,
            "saliency_map": saliency_map,
        }

    def get_explain_fn(self) -> Callable:
        """Returns explain function."""
        explainer = ViTReciproCAM(
            self.head_forward_fn,
            num_classes=self.num_classes,
        )
        return explainer.func

    @property
    def _optimization_config(self) -> dict[str, Any]:
        """PTQ config for DeitTinyForMultilabelCls."""
        return {"model_type": "transformer"}


class DeitTinyForHLabelCls(ForwardExplainMixInForDeit, MMPretrainHlabelClsModel):
    """DeitTiny Model for hierarchical label classification task."""

    def __init__(
        self,
        label_info: HLabelInfo,
        optimizer: OptimizerCallable = DefaultOptimizerCallable,
        scheduler: LRSchedulerCallable | LRSchedulerListCallable = DefaultSchedulerCallable,
        metric: MetricCallable = HLabelClsMetricCallble,
        torch_compile: bool = False,
    ) -> None:
        config = read_mmconfig("deit_tiny", subdir_name="hlabel_classification")

        super().__init__(
            label_info=label_info,
            config=config,
            optimizer=optimizer,
            scheduler=scheduler,
            metric=metric,
            torch_compile=torch_compile,
        )

    def load_from_otx_v1_ckpt(self, state_dict: dict, add_prefix: str = "model.model.") -> dict:
        """Load the previous OTX ckpt according to OTX2.0."""
        return OTXv1Helper.load_cls_effnet_b0_ckpt(state_dict, "multiclass", add_prefix)


class DeitTinyForMulticlassCls(ForwardExplainMixInForDeit, MMPretrainMulticlassClsModel):
    """DeitTiny Model for multi-label classification task."""

    def __init__(
        self,
        label_info: LabelInfoTypes,
        optimizer: OptimizerCallable = DefaultOptimizerCallable,
        scheduler: LRSchedulerCallable | LRSchedulerListCallable = DefaultSchedulerCallable,
        metric: MetricCallable = MultiClassClsMetricCallable,
        torch_compile: bool = False,
    ) -> None:
        config = read_mmconfig("deit_tiny", subdir_name="multiclass_classification")
        super().__init__(
            label_info=label_info,
            config=config,
            optimizer=optimizer,
            scheduler=scheduler,
            metric=metric,
            torch_compile=torch_compile,
        )

    def load_from_otx_v1_ckpt(self, state_dict: dict, add_prefix: str = "model.model.") -> dict:
        """Load the previous OTX ckpt according to OTX2.0."""
        return OTXv1Helper.load_cls_effnet_b0_ckpt(state_dict, "multiclass", add_prefix)


class DeitTinyForMultilabelCls(ForwardExplainMixInForDeit, MMPretrainMultilabelClsModel):
    """DeitTiny Model for multi-class classification task."""

    def __init__(
        self,
        label_info: LabelInfoTypes,
        optimizer: OptimizerCallable = DefaultOptimizerCallable,
        scheduler: LRSchedulerCallable | LRSchedulerListCallable = DefaultSchedulerCallable,
        metric: MetricCallable = MultiLabelClsMetricCallable,
        torch_compile: bool = False,
    ) -> None:
        config = read_mmconfig("deit_tiny", subdir_name="multilabel_classification")
        super().__init__(
            label_info=label_info,
            config=config,
            optimizer=optimizer,
            scheduler=scheduler,
            metric=metric,
            torch_compile=torch_compile,
        )

    def load_from_otx_v1_ckpt(self, state_dict: dict, add_prefix: str = "model.model.") -> dict:
        """Load the previous OTX ckpt according to OTX2.0."""
        return OTXv1Helper.load_cls_effnet_b0_ckpt(state_dict, "multiclass", add_prefix)
