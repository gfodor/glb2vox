from cog import BasePredictor, Input, Path
import torch
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cog_flux'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hunyuan3d_2'))

from cog_flux.predict import DevPredictor
from hunyuan3d_2.predict import Predictor as HunyuanPredictor

class PipelinePredictor(BasePredictor):
    def setup(self):
        # Initialize Flux dev predictor
        self.flux_predictor = DevPredictor()
        self.flux_predictor.setup()
        # Initialize Hunyuan3D-2 predictor
        self.hunyuan_predictor = HunyuanPredictor()
        self.hunyuan_predictor.setup()

    def predict(
        self,
        prompt: str = Input(description="Prompt for generated image"),
        seed: int = Input(description="Random seed", default=1234),
        num_inference_steps: int = Input(description="Number of inference steps for Flux", default=28, ge=1, le=50),
        guidance: float = Input(description="Guidance scale for Flux", default=3.0, ge=0.0, le=10.0),
        prompt_strength: float = Input(description="Prompt strength for img2img in Flux (only applicable if image is provided)", default=0.8, ge=0.0, le=1.0),
        steps: int = Input(description="Number of inference steps for Hunyuan", default=50, ge=20, le=50),
        guidance_scale: float = Input(description="Guidance scale for Hunyuan", default=5.5, ge=1.0, le=20.0),
        octree_resolution: int = Input(description="Octree resolution for Hunyuan", choices=[256, 384, 512], default=512),
        resolution: int = Input(description="Voxel resolution for glb2vox", default=96),
    ) -> Path:
        # Generate image using Flux dev
        flux_output = self.flux_predictor.predict(
            prompt=prompt,
            aspect_ratio="1:1",
            num_outputs=1,
            num_inference_steps=num_inference_steps,
            guidance=guidance,
            seed=seed,
            output_format="png",
            output_quality=100,
            disable_safety_checker=True,
            go_fast=False,
            megapixels="1",
            image=None,
            prompt_strength=prompt_strength,
        )
        image_path = flux_output[0]

        # Generate GLB using Hunyuan3D-2
        hunyuan_output = self.hunyuan_predictor.predict(
            image=image_path,
            steps=steps,
            guidance_scale=guidance_scale,
            seed=seed,
            octree_resolution=octree_resolution,
            remove_background=False,
        )
        glb_path = hunyuan_output.mesh

        # Convert GLB to VOX using glb2vox.sh
        vox_path = self.run_glb2vox(glb_path, resolution)
        return Path(vox_path)

    def run_glb2vox(self, glb_path, resolution):
        # Execute the glb2vox.sh script with resolution
        subprocess.run(["bash", "./glb2vox.sh", str(glb_path), str(resolution)], check=True)
        # Compute the VOX output path based on the GLB input path
        vox_path = str(glb_path).replace('.glb', '.vox')
        return vox_path