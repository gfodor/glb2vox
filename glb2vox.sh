#!/bin/bash

# Check if a file path, resolution, and output_vox were provided
if [ $# -ne 3 ]; then
  echo "Usage: $0 /path/to/model.glb resolution /path/to/output.vox"
  exit 1
fi

# Get the input file, resolution, and output_vox
INPUT_FILE="$1"
RESOLUTION="$2"
OUTPUT_VOX="$3"

# Extract basename from INPUT_FILE for intermediate files
BASENAME=$(basename "$INPUT_FILE" .glb)
DIRNAME=$(dirname "$INPUT_FILE")
WORKING_DIR="$DIRNAME"

# Make sure input file exists and is a GLB file
if [ ! -f "$INPUT_FILE" ] || [[ "$INPUT_FILE" != *.glb ]]; then
  echo "Error: Input file must be a valid .glb file"
  exit 1
fi

cd "$WORKING_DIR"

echo "Extracting textures from $BASENAME.glb..."
assimp extract "$BASENAME.glb" textures

echo "Exporting to OBJ format..."
assimp export "$BASENAME.glb" "${BASENAME}_with_textures.obj" -ptv

echo "Fixing texture references in MTL file..."
sed -i '' -e 's/map_Kd \*0/map_Kd textures_img0.png/g' "${BASENAME}_with_textures.mtl"

# Get dir this script is in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Converting to VOX format with resolution $RESOLUTION..."
wine $DIR/../poly2vox.exe /v$RESOLUTION /t "${BASENAME}_with_textures.mtl" "${BASENAME}_with_textures.obj" "$OUTPUT_VOX"

echo "Generating SVOX and GLTF..."
$DIR/../vox2svox "$OUTPUT_VOX" "${OUTPUT_VOX}.svox"
$DIR/../svox2gltf "${OUTPUT_VOX}.svox" "${OUTPUT_VOX}.gltf"

echo "Cleaning up intermediate files..."
rm -f "${BASENAME}_with_textures.obj" "${BASENAME}_with_textures.mtl" textures_img*.png

echo "Conversion complete: $OUTPUT_VOX and ${OUTPUT_VOX}.gltf"