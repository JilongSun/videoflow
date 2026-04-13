from .slice_replace import SliceReplaceWorkflow
from .subject_mask_replace import SubjectMaskReplaceWorkflow


WORKFLOW_REGISTRY = {
    SliceReplaceWorkflow.name: SliceReplaceWorkflow,
    SubjectMaskReplaceWorkflow.name: SubjectMaskReplaceWorkflow,
}


def get_workflow_cls(workflow_type: str):
    if workflow_type not in WORKFLOW_REGISTRY:
        supported = ", ".join(WORKFLOW_REGISTRY.keys())
        raise ValueError(f"unsupported workflow_type={workflow_type!r}, supported: {supported}")
    return WORKFLOW_REGISTRY[workflow_type]
