"""Combined Railway sidecar for Food Gate, SigLIP hints, and segmentation."""

from ml.inference.food_gate import create_app as create_food_gate_app
from ml.serving.segment_server import app as segment_app
from ml.serving.siglip_food_hint_routes import attach_siglip_food_hint_routes


app = create_food_gate_app()
attach_siglip_food_hint_routes(app)

# Keep the existing Railway sticker API contract. The public GPU-only app
# intentionally does not mount this route.
app.mount("/segment", segment_app)
