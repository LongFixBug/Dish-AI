"""Combined ML sidecar for the Railway free-plan service slot.

Food Gate and sticker segmentation are separate HTTP contracts but share one
container because Railway's trial plan limits the number of services.  The
segmentation app is mounted lazily and does not load U2Net until a sticker is
actually requested; Food Gate keeps its existing startup readiness contract.
"""

from fastapi import FastAPI

from ml.inference.food_gate import create_app as create_food_gate_app
from ml.serving.segment_server import app as segment_app


app: FastAPI = create_food_gate_app()
app.mount("/segment", segment_app)
