# TEXT2VOX: 3D Voxel Model Generator

TEXT2VOX is a Cog service that generates MagicaVoxel VOX files from text prompts. It combines state-of-the-art AI models to create detailed voxel models that can be used in games, 3D visualization, and creative projects.

## Overview

This pipeline uses two AI models in sequence:
1. **Flux** - A text-to-image model that generates a 3D-style reference image
2. **Hunyuan3D-2** - A 3D model generator that creates a GLB file from the image
3. **GLB2VOX Converter** - Converts the GLB model to MagicaVoxel VOX format at different resolutions

## Features

- Generate voxel models from simple text descriptions
- Control the detail level (high or low)
- Multiple resolutions output simultaneously
- Includes both VOX files and GLB/GLTF versions

## Usage

### Basic Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `prompt` | Text description of the 3D model you want to create | (Required) |
| `detail_level` | Detail level of the model (`high` or `low`) | `high` |

### Detail Level and Resolutions

The service provides different resolution outputs based on the chosen detail level, which drives the generation:

- **High Detail**: Optimized for detailed models
  - Large: 96×96×96 voxels
  - Medium: 80×80×80 voxels
  - Small: 64×64×64 voxels

- **Low Detail**: Optimized for blocky, Minecraft-style models
  - Large: 64×64×64 voxels
  - Medium: 48×48×48 voxels
  - Small: 32×32×32 voxels

### Output Files

For each generation, you'll receive:
- Multiple VOX files at different resolutions
- A GLB file representation of the voxel model
- A GLTF file for web viewing

All files are named based on your prompt (converted to snake_case) with size suffixes.
