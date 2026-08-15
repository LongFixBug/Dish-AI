"""Public GPU sidecar: Food Gate and SigLIP food hints only.

Sticker segmentation is deliberately absent so a public RunPod endpoint does
not expose an unrelated, GPU-expensive operation.
"""

from ml.inference.food_gate import create_app as create_food_gate_app
from ml.serving.siglip_food_hint_routes import attach_siglip_food_hint_routes


app = create_food_gate_app()
attach_siglip_food_hint_routes(app)
