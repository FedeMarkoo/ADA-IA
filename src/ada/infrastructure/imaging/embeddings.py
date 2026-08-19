import os
import io
import numpy as np
from PIL import Image

import json

_CONFIG = None
_IMAGE_MODEL = None
_TEXT_MODEL = None
_FALLBACK_MODEL = None
def _load_config():
    global _CONFIG
    if _CONFIG is None:
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'config.json')
            with open(cfg_path, 'r') as f:
                _CONFIG = json.load(f)
        except Exception:
            _CONFIG = {'max_threads': 4, 'use_mps': False}
    return _CONFIG

def _configure_torch():
    cfg = _load_config()
    try:
        import torch
        torch.set_num_threads(cfg.get('max_threads', 4))
        if cfg.get('use_mps', False) and getattr(torch, 'has_mps', False):
            # user can still choose device when creating tensors/models
            pass
    except Exception:
        pass


_configure_torch()
def _load_image(path):
    return Image.open(path).convert('RGB')

def embed_image_sentence_transformers(model, path):
    try:
        img = _load_image(path)
        emb = model.encode(img, convert_to_numpy=True)
        return emb
    except Exception:
        return None

def get_image_embedding(path):
    global _IMAGE_MODEL, _FALLBACK_MODEL
    try:
        from sentence_transformers import SentenceTransformer
        if _IMAGE_MODEL is None:
            _IMAGE_MODEL = SentenceTransformer('clip-ViT-B-32')
        emb = embed_image_sentence_transformers(_IMAGE_MODEL, path)
        return emb
    except Exception:
        try:
            import torch
            import torchvision.transforms as T
            from torchvision.models import resnet18

            img = _load_image(path)
            preprocess = T.Compose([T.Resize(256), T.CenterCrop(224), T.ToTensor()])
            x = preprocess(img).unsqueeze(0)
            if _FALLBACK_MODEL is None:
                _FALLBACK_MODEL = resnet18(pretrained=True)
                _FALLBACK_MODEL.eval()
            with torch.no_grad():
                model = _FALLBACK_MODEL
                feat = model.avgpool(model.layer4(model.layer3(model.layer2(model.layer1(model.relu(model.bn1(model.conv1(x))))))))
                vec = feat.squeeze().numpy()
            return vec
        except Exception:
            return None

def get_text_embedding(text):
    global _TEXT_MODEL
    # Lazy import sentence-transformers for text embeddings
    try:
        from sentence_transformers import SentenceTransformer
        if _TEXT_MODEL is None:
            _TEXT_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        emb = _TEXT_MODEL.encode(text, convert_to_numpy=True)
        return emb
    except Exception:
        try:
            # last-resort: simple hashing to fixed vector (deterministic but poor)
            import hashlib
            import numpy as _np
            h = hashlib.sha256(text.encode('utf-8')).digest()
            arr = _np.frombuffer(h, dtype=_np.uint8).astype('float32')
            # pad/trim to dim
            dim = 512
            out = _np.zeros(dim, dtype='float32')
            out[:len(arr)] = arr
            return out
        except Exception:
            return None
