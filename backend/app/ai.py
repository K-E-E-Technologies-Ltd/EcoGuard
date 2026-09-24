"""Optional, real TorchVision inference. No weights => unavailable, never random labels.
Expected checkpoint: Faster R-CNN ResNet50 FPN state_dict trained for supplied labels.
Only operator-controlled local paths are loaded. See docs/AI.md for training/evaluation.
"""
from pathlib import Path
from functools import lru_cache
import io,json
from PIL import Image
from .config import get_settings

@lru_cache(maxsize=1)
def load_model():
    cfg=get_settings()
    if not cfg.model_path or not cfg.model_labels_path:return None
    import torch
    from torchvision.models.detection import fasterrcnn_resnet50_fpn
    labels=json.loads(Path(cfg.model_labels_path).read_text())
    if not isinstance(labels,list) or len(labels)<2 or labels[0]!='__background__':
        raise ValueError('Labels must be a list beginning with __background__.')
    model=fasterrcnn_resnet50_fpn(weights=None,weights_backbone=None,num_classes=len(labels))
    model.load_state_dict(torch.load(cfg.model_path,map_location='cpu',weights_only=True))
    model.eval()
    return model,labels

def infer(data):
    cfg=get_settings();bundle=load_model()
    if bundle is None:
        return dict(state='unavailable',species=None,confidence=None,boxes=[],model_version='not-configured',
            explanation='No evaluated wildlife model is configured. Continue as unknown or enter your observation; human review is required.')
    import torch
    from torchvision.transforms.functional import to_tensor
    model,labels=bundle
    image=Image.open(io.BytesIO(data)).convert('RGB')
    with torch.inference_mode():result=model([to_tensor(image)])[0]
    candidates=[]
    for score,label,box in zip(result['scores'].tolist(),result['labels'].tolist(),result['boxes'].tolist()):
        if score>=cfg.confidence_threshold and 0<label<len(labels):
            candidates.append({'species':labels[label],'confidence':score,'box':box})
    best=candidates[0] if candidates else None
    return dict(state='completed' if best else 'unknown',species=best['species'] if best else None,
        confidence=best['confidence'] if best else None,boxes=candidates[:10],model_version=cfg.model_version,
        explanation='Candidate identification only; an authorised reviewer must assess the report.' if best else 'No candidate passed the configured threshold. Unknown is a valid result.')
