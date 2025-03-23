from cog import BasePredictor, Input, Path
import torch
import os
import subprocess
from pipeline.cog_flux.predict import DevPredictor
from pipeline.hunyuan3d_2.predict import Predictor as HunyuanPredictor

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
        seed: int = Input(description="Random seed", default=None),
    ) -> Path:
        # Default parameters for Flux dev
        aspect_ratio = "1:1"
        num_outputs = 1
        num_inference_steps = 28
        guidance = 3.0
        go_fast = True
        megapixels = "1"
        output_format = "png"
        output_quality = 100
        disable_safety_checker = True  # Intermediate step, safety check not needed

        # Generate image using Flux dev
        flux_output = self.flux_predictor.predict(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            num_outputs=num_outputs,
            num_inference_steps=num_inference_steps,
            guidance=guidance,
            seed=seed,
            output_format=output_format,
            output_quality=output_quality,
            disable_safety_checker=disable_safety_checker,
            go_fast=go_fast,
            megapixels=megapixels,
        )
        image_path = flux_output[0]

        # Generate GLB using Hunyuan3D-2
        hunyuan_output = self.hunyuan_predictor.predict(
            image=image_path,
            steps=50,
            guidance_scale=5.5,
            seed=seed,
            octree_resolution=512,
            remove_background=False,  # Generated image likely has no background
        )
        glb_path = hunyuan_output.mesh

        # Convert GLB to VOX using glb2vox.sh
        vox_path = self.run_glb2vox(glb_path)
        return Path(vox_path)

    def run_glb2vox(self, glb_path):
        # Execute the glb2vox.sh script
        subprocess.run(["bash", "./glb2vox.sh", str(glb_path)], check=True)
        # Compute the VOX output path based on the GLB input path
        vox_path = str(glb_path).replace('.glb', '.vox')
        return vox_path
