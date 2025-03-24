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
        detail_level: str = Input(description="Detail level. High will try to generate a good high resolution voxel model, and low try to generate a good low resolution voxel model.", choices=["low", "high"], default="high"),
        seed: int = Input(description="Random seed", default=1234),
        num_inference_steps: int = Input(description="Number of inference steps for Flux", default=50, ge=1, le=50),
        guidance: float = Input(description="Guidance scale for Flux", default=6.0, ge=0.0, le=10.0),
        prompt_strength: float = Input(description="Prompt strength for img2img in Flux (only applicable if image is provided)", default=0.8, ge=0.0, le=1.0),
        steps: int = Input(description="Number of inference steps for Hunyuan", default=50, ge=20, le=50),
        guidance_scale: float = Input(description="Guidance scale for Hunyuan", default=5.5, ge=1.0, le=20.0),
        octree_resolution: int = Input(description="Octree resolution for Hunyuan", choices=[256, 384, 512], default=512),
        remove_background: bool = Input(description="Remove the background from the generated image. Useful to turn off if you want to generate a full voxel scene.", default=True),
    ) -> list[Path]:
        # Generate snake_case filename from prompt
        def to_snake_case(text):
            # Convert to lowercase
            text = text.lower()
            # Replace spaces and special characters with underscores
            text = ''.join(c if c.isalnum() else '_' for c in text)
            # Replace multiple underscores with a single one
            text = '_'.join(filter(None, text.split('_')))
            # Ensure it doesn't start with a digit
            if text and text[0].isdigit():
                text = 'obj_' + text
            # Limit length to prevent excessively long filenames
            return text[:50]
            
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
            remove_background=remove_background,
        )
        glb_path = hunyuan_output.mesh

        # Create a descriptive filename base from the prompt
        filename_base = to_snake_case(prompt)
        output_dir = os.path.dirname(glb_path)
        
        # Determine resolutions based on detail_level
        if detail_level == "high":
            resolutions = [96, 80, 64]
        elif detail_level == "low":
            resolutions = [64, 48, 32]
        sizes = ['large', 'medium', 'small']
        temp_base = os.path.splitext(glb_path)[0]
        
        # First run the conversions with temporary filenames
        temp_vox_paths = []
        for size, res in zip(sizes, resolutions):
            temp_output_vox = f"{temp_base}_{size}.vox"
            self.run_glb2vox(glb_path, res, temp_output_vox)
            temp_vox_paths.append(temp_output_vox)
        
        # Create output filenames with descriptive names
        final_glb_path = os.path.join(output_dir, f"{filename_base}.vox.glb")
        final_vox_paths = []
        
        # Rename the files to use descriptive filenames
        for size, temp_vox_path in zip(sizes, temp_vox_paths):
            final_vox_path = os.path.join(output_dir, f"{filename_base}_{size}.vox")
            os.rename(temp_vox_path, final_vox_path)
            final_vox_paths.append(final_vox_path)
            
            # Also rename the .gltf file for the first one (large)
            if size == 'large':
                temp_gltf_path = f"{temp_vox_path}.gltf"
                temp_glb_path = f"{temp_vox_path}.glb"
                final_gltf_path = os.path.join(output_dir, f"{filename_base}.vox.gltf")
                os.rename(temp_gltf_path, final_gltf_path)
                os.rename(temp_glb_path, final_glb_path)
        
        # Return the final paths
        return [Path(final_glb_path)] + [Path(vox_path) for vox_path in final_vox_paths]

    def run_glb2vox(self, glb_path, resolution, output_vox):
        subprocess.run(["bash", "./glb2vox.sh", str(glb_path), str(resolution), str(output_vox)], check=True)
