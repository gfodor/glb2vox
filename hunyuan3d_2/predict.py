from cog import BasePredictor, BaseModel, Input, Path
from torch import Generator
import os
from PIL import Image
import time
import subprocess
import shutil
from hy3dgen.shapegen import FaceReducer, FloaterRemover, DegenerateFaceRemover, Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.shapegen.models.autoencoders import SurfaceExtractors
from hy3dgen.shapegen.utils import logger
from hy3dgen.rembg import BackgroundRemover
from hy3dgen.texgen import Hunyuan3DPaintPipeline

CHECKPOINTS_PATH = "/src/checkpoints"
HUNYUAN3D_REPO = "tencent/Hunyuan3D-2"
HUNYUAN3D_MODEL = "hunyuan3d-dit-v2-0-turbo"
HUNYUAN3D_VAE_MODEL = "hunyuan3d-vae-v2-0-turbo"
HUNYUAN3D_PATH = os.path.join(CHECKPOINTS_PATH, HUNYUAN3D_REPO)
U2NET_PATH = os.path.join(CHECKPOINTS_PATH, ".u2net/")
DELIGHT_URL = "https://weights.replicate.delivery/default/tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0/delight.tar"
PAINT_URL = "https://weights.replicate.delivery/default/tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0/paint.tar"
U2NET_URL = "https://weights.replicate.delivery/default/comfy-ui/rembg/u2net.onnx.tar"

def download_if_not_exists(url, dest):
    if not os.path.exists(dest):
        start = time.time()
        os.makedirs(dest, exist_ok=True)
        logger.info(f"downloading url: {url}") 
        logger.info(f"downloading to: {dest}")
        subprocess.check_call(["pget", "-xf", url, dest], close_fds=False)
        duration = time.time() - start
        logger.info(f"downloading took: {duration:.2f}s")

class Output(BaseModel):
    mesh: Path

class Predictor(BasePredictor):
    def setup(self) -> None:
        logger.info("Setting up environment")
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ['U2NET_HOME'] = U2NET_PATH
        os.environ["HY3DGEN_MODELS"] = CHECKPOINTS_PATH
        os.makedirs(os.path.join(HUNYUAN3D_PATH, HUNYUAN3D_MODEL), exist_ok=True)

        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id=HUNYUAN3D_REPO,
            filename=f"{HUNYUAN3D_MODEL}/model.fp16.safetensors",
            repo_type="model",
            local_dir=HUNYUAN3D_PATH  
        )
        hf_hub_download(
            repo_id=HUNYUAN3D_REPO,
            filename=f"{HUNYUAN3D_MODEL}/config.yaml",
            repo_type="model",
            local_dir=HUNYUAN3D_PATH
        )

        hf_hub_download(
            repo_id=HUNYUAN3D_REPO,
            filename=f"{HUNYUAN3D_VAE_MODEL}/model.fp16.safetensors",
            repo_type="model",
            local_dir=HUNYUAN3D_PATH  
        )
        hf_hub_download(
            repo_id=HUNYUAN3D_REPO,
            filename=f"{HUNYUAN3D_VAE_MODEL}/config.yaml",
            repo_type="model",
            local_dir=HUNYUAN3D_PATH
        )

        download_if_not_exists(DELIGHT_URL, os.path.join(HUNYUAN3D_PATH, "hunyuan3d-delight-v2-0"))
        download_if_not_exists(PAINT_URL, os.path.join(HUNYUAN3D_PATH, "hunyuan3d-paint-v2-0"))
        download_if_not_exists(U2NET_URL, U2NET_PATH)
        self.i23d_worker = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            HUNYUAN3D_REPO,
            subfolder=HUNYUAN3D_MODEL
        )
        self.i23d_worker.enable_flashvdm(mc_algo='mc')
        self.i23d_worker.vae.surface_extractor = SurfaceExtractors['mc']()
        self.texgen_worker = Hunyuan3DPaintPipeline.from_pretrained(HUNYUAN3D_REPO)
        self.floater_remove_worker = FloaterRemover()
        self.degenerate_face_remove_worker = DegenerateFaceRemover()
        self.face_reduce_worker = FaceReducer()
        self.rmbg_worker = BackgroundRemover()
        logger.info("Finished setting up environment")

    def predict(
        self,
        image: Path = Input(
            description="Input image for generating 3D shape",
            default=None
        ),
        steps: int = Input(
            description="Number of inference steps",
            default=50,
            ge=20,
            le=50,
        ),
        guidance_scale: float = Input(
            description="Guidance scale for generation",
            default=5.5,
            ge=1.0,
            le=20.0,
        ),
        seed: int = Input(
            description="Random seed for generation",
            default=1234
        ),
        octree_resolution: int = Input(
            description="Octree resolution for mesh generation",
            choices=[256, 384, 512],
            default=512
        ),
        remove_background: bool = Input(
            description="Whether to remove background from input image",
            default=True
        ),
    ) -> Output:
        if os.path.exists("output"):
            shutil.rmtree("output")
        
        os.makedirs("output", exist_ok=True)

        max_facenum = 40000

        generator = Generator()
        generator = generator.manual_seed(seed)

        if image is not None:
            input_image = Image.open(str(image))
            if remove_background or input_image.mode == "RGB":
                input_image = self.rmbg_worker(input_image.convert('RGB'))
        else:
            raise ValueError("Image must be provided")

        input_image.save("output/input.png")

        mesh = self.i23d_worker(
            image=input_image,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=generator,
            octree_resolution=octree_resolution,
            num_chunks=200000
        )[0]

        mesh = self.floater_remove_worker(mesh)
        mesh = self.degenerate_face_remove_worker(mesh)
        mesh = self.face_reduce_worker(mesh, max_facenum=max_facenum)
        mesh = self.texgen_worker(mesh, input_image)
        output_path = Path("output/mesh.glb")
        mesh.export(str(output_path), include_normals=True)

        if not Path(output_path).exists():
            raise RuntimeError(f"Failed to generate mesh file at {output_path}")

        return Output(mesh=output_path)
