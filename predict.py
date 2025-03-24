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
        guidance: float = Input(description="Guidance scale for Flux", default=6.0, ge=0.0, le=10.0),
        prompt_strength: float = Input(description="Prompt strength for img2img in Flux (only applicable if image is provided)", default=0.8, ge=0.0, le=1.0),
        steps: int = Input(description="Number of inference steps for Hunyuan", default=50, ge=20, le=50),
        guidance_scale: float = Input(description="Guidance scale for Hunyuan", default=5.5, ge=1.0, le=20.0),
        octree_resolution: int = Input(description="Octree resolution for Hunyuan", choices=[256, 384, 512], default=512),
        detail_level: str = Input(description="Detail level", choices=["low", "high"], default="high"),
    ) -> list[Path]:
        # Modify prompt based on detail_level
        if detail_level == "high":
            template = "A high quality iconic 3/4 perspective 3D render of {} in a cel shaded game engine."
        elif detail_level == "low":
            template = "A isometric view of {} made out of large Minecraft cubes. Black background, floating in space."
        else:
            raise ValueError("Invalid detail_level")
        words = prompt.split()
        if words:
            words[0] = words[0][0].lower() + words[0][1:]
            modified_prompt = ' '.join(words)
        else:
            modified_prompt = prompt
        final_prompt = template.format(modified_prompt)

        # Generate image using Flux dev
        flux_output = self.flux_predictor.predict(
            prompt=final_prompt,
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

        # Determine resolutions based on detail_level
        if detail_level == "high":
            resolutions = [96, 80, 64]
        elif detail_level == "low":
            resolutions = [48, 32, 24]
        sizes = ['large', 'medium', 'small']
        base = os.path.splitext(glb_path)[0]
        for size, res in zip(sizes, resolutions):
            output_vox = f"{base}_{size}.vox"
            self.run_glb2vox(glb_path, res, output_vox)

        # Compute paths for output
        gltf_path = f"{base}_large.vox.gltf"
        vox_paths = [f"{base}_{size}.vox" for size in sizes]
        return [Path(gltf_path)] + [Path(vox_path) for vox_path in vox_paths]

    def run_glb2vox(self, glb_path, resolution, output_vox):
        subprocess.run(["bash", "./glb2vox.sh", str(glb_path), str(resolution), str(output_vox)], check=True)